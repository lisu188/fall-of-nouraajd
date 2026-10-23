/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "core/CSceneManager.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CProvider.h"
#include "object/CPlayer.h"
#include <stdexcept>

namespace {
void finishCallback(const std::function<void(bool)> &callback, bool success) noexcept {
    if (!callback) {
        return;
    }
    try {
        callback(success);
    } catch (const std::exception &error) {
        vstd::logger::error("Map transition completion callback failed:", error.what());
    } catch (...) {
        vstd::logger::error("Map transition completion callback failed");
    }
}

void finishRequest(const CMapTransitionRequest &request, bool success) { finishCallback(request.onFinished, success); }
} // namespace

scene_detail::CTransitionCompletion::CTransitionCompletion(std::function<void(bool)> callback)
    : callback(std::move(callback)) {}

scene_detail::CTransitionCompletion::~CTransitionCompletion() { finish(false); }

void scene_detail::CTransitionCompletion::finish(bool success) noexcept {
    if (!settled.exchange(true, std::memory_order_acq_rel)) {
        auto invocation = std::move(callback);
        finishCallback(invocation, success);
    }
}

bool CSceneManager::requestMapChange(const std::shared_ptr<CGame> &game, std::string mapName) {
    CMapTransitionRequest request;
    request.targetMap = std::move(mapName);
    return requestMapChange(game, std::move(request));
}

bool CSceneManager::requestMapChange(const std::shared_ptr<CGame> &game, CMapTransitionRequest request) {
    return requestMapChange(game, std::move(request), {});
}

bool CSceneManager::requestMapChange(const std::shared_ptr<CGame> &game, CMapTransitionRequest request,
                                     vstd::move_only_function<vstd::task<void>()> beforeEntryAsync) {
    const std::string mapName = request.targetMap;
    if (!game) {
        if (CPlaytestTrace::enabled()) {
            CPlaytestTrace::record("map_transition_rejected", {{"reason", "missing_game"}, {"toMap", mapName}});
        }
        vstd::logger::warning("Rejected map transition without a game:", mapName);
        finishRequest(request, false);
        return false;
    }
    if (game->getSceneManager().get() != this) {
        if (CPlaytestTrace::enabled()) {
            json fields = {{"reason", "mismatched_scene_manager"}, {"toMap", mapName}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("map_transition_rejected", fields);
        }
        vstd::logger::warning("Rejected map transition for a mismatched scene manager:", mapName);
        finishRequest(request, false);
        return false;
    }
    if (transitionState != TransitionState::Idle) {
        if (CPlaytestTrace::enabled()) {
            json fields = {
                {"pendingMap", pendingMapName},
                {"reason", "transition_pending"},
                {"toMap", mapName},
                {"transitionState", getTransitionStateName()},
            };
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("map_transition_rejected", fields);
        }
        vstd::logger::warning("Ignoring duplicate map transition request:", mapName, "while pending:", pendingMapName);
        finishRequest(request, false);
        return false;
    }

    transitionState = TransitionState::TransitionPending;
    pendingMapName = mapName;
    auto context = game->getContext();
    if (!context->isActive()) {
        resetTransition();
        finishRequest(request, false);
        return false;
    }
    context->advanceTransitionGeneration();
    const auto expectedGeneration = context->captureTransitionGeneration();
    pendingGeneration = expectedGeneration;
    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"accepted", true},
            {"retainSourceMap", request.retainSourceMap},
            {"reuseLoadedMap", request.reuseLoadedMap},
            {"toMap", mapName},
            {"transitionState", getTransitionStateName()},
        };
        CPlaytestTrace::addMapContext(fields, game->getMap());
        CPlaytestTrace::record("map_transition_requested", fields);
    }

    auto manager = shared_from_this();
    std::weak_ptr<CGame> weakGame = game;
    std::weak_ptr<CGameContext> weakContext = context;
    std::weak_ptr<CMap> weakExpectedMap = game->getMap();
    const bool hadExpectedMap = game->getMap() != nullptr;
    auto completion = std::make_shared<scene_detail::CTransitionCompletion>(std::move(request.onFinished));
    try {
        context->spawnTask(runTransitionAsync(manager, weakGame, weakContext, weakExpectedMap, hadExpectedMap,
                                              expectedGeneration, std::move(request), std::move(beforeEntryAsync),
                                              completion));
    } catch (...) {
        if (pendingGeneration == expectedGeneration) {
            resetTransition();
        }
        completion->finish(false);
        throw;
    }
    return true;
}

vstd::task<void> CSceneManager::runTransitionAsync(std::shared_ptr<CSceneManager> manager,
                                                   std::weak_ptr<CGame> weakGame,
                                                   std::weak_ptr<CGameContext> weakContext,
                                                   std::weak_ptr<CMap> weakExpectedMap, bool hadExpectedMap,
                                                   std::uint64_t expectedGeneration, CMapTransitionRequest request,
                                                   vstd::move_only_function<vstd::task<void>()> beforeEntryAsync,
                                                   std::shared_ptr<scene_detail::CTransitionCompletion> completion) {
    const auto targetMap = request.targetMap;
    auto reject = [&] {
        if (manager->transitionState == TransitionState::TransitionPending && manager->pendingMapName == targetMap &&
            manager->pendingGeneration == expectedGeneration) {
            manager->resetTransition();
        }
        completion->finish(false);
    };
    auto valid = [&] {
        auto game = weakGame.lock();
        auto context = weakContext.lock();
        auto expected_map = weakExpectedMap.lock();
        return game && context && context->isTransitionGenerationCurrent(expectedGeneration) &&
               (!hadExpectedMap || (expected_map && game->getMap() == expected_map)) &&
               manager->transitionState == TransitionState::TransitionPending &&
               manager->pendingMapName == request.targetMap && manager->pendingGeneration == expectedGeneration;
    };
    try {
        co_await vstd::post(vstd::event_loop<>::instance());
        if (!valid()) {
            reject();
            co_return;
        }
        co_await vstd::until(vstd::event_loop<>::instance(), [&] {
            auto game = weakGame.lock();
            return !valid() || !game || !game->getMap() || !game->getMap()->isMoving();
        });
        if (!valid()) {
            reject();
            co_return;
        }
        co_await manager->performMapChangeAsync(weakGame, expectedGeneration, std::move(request),
                                                std::move(beforeEntryAsync), completion);
    } catch (const vstd::task_cancelled &) {
        reject();
    } catch (const vstd::scheduler_rejected &) {
        reject();
        throw;
    } catch (const std::exception &error) {
        reject();
        vstd::logger::error("Map transition failed:", error.what());
    } catch (...) {
        reject();
        throw;
    }
}

bool CSceneManager::isTransitionPending() const { return transitionState != TransitionState::Idle; }

CSceneManager::TransitionState CSceneManager::getTransitionState() const { return transitionState; }

std::string CSceneManager::getTransitionStateName() const {
    switch (transitionState) {
    case TransitionState::Idle:
        return "Idle";
    case TransitionState::TransitionPending:
        return "TransitionPending";
    case TransitionState::Transitioning:
        return "Transitioning";
    }
    return "Unknown";
}

std::string CSceneManager::getPendingMapName() const { return pendingMapName; }

vstd::task<void> CSceneManager::performMapChangeAsync(std::weak_ptr<CGame> weakGame, std::uint64_t expectedGeneration,
                                                      CMapTransitionRequest request,
                                                      vstd::move_only_function<vstd::task<void>()> beforeEntryAsync,
                                                      std::shared_ptr<scene_detail::CTransitionCompletion> completion) {
    auto game = weakGame.lock();
    if (!game || !game->getContext()->isTransitionGenerationCurrent(expectedGeneration)) {
        resetTransition();
        completion->finish(false);
        co_return;
    }
    const std::string &mapName = request.targetMap;
    const auto oldMap = game->getMap();
    const auto oldScope = game->getResourcesProvider()->getActiveScope();
    const auto player = oldMap ? oldMap->getPlayer() : nullptr;
    const auto oldCoords = player ? player->getCoords() : Coords();
    const auto oldController = player ? player->getController() : nullptr;
    const auto oldFightController = player ? player->getFightController() : nullptr;
    std::shared_ptr<CMap> map;
    try {
        transitionState = TransitionState::Transitioning;
        json traceFields = json::object();
        if (player) {
            player->captureQuestJournal();
        }
        if (CPlaytestTrace::enabled()) {
            traceFields["fromMap"] = oldMap ? oldMap->getMapName() : "";
            traceFields["oldTurn"] = oldMap ? oldMap->getTurn() : 0;
            traceFields["toMap"] = mapName;
        }
        bool reusedSession = false;
        std::optional<Coords> retainedReturnCoords;
        if (request.reuseLoadedMap) {
            auto store = game->getContext()->getMapSessionStore();
            std::string matchedAnchor = request.returnAnchor;
            map = store->get(mapName, matchedAnchor);
            if (!map && !request.returnAnchor.empty()) {
                matchedAnchor.clear();
                map = store->get(mapName);
            }
            if (map) {
                retainedReturnCoords = store->getReturnCoords(mapName, matchedAnchor);
            }
            reusedSession = map != nullptr;
        }
        if (!map) {
            map = CMapLoader::loadNewMap(game, mapName);
        }
        if (!game->getContext()->isTransitionGenerationCurrent(expectedGeneration) ||
            (game->getMap() != oldMap && game->getMap() != map) || (oldMap && oldMap->getPlayer() != player)) {
            throw std::runtime_error("The game session changed while loading the destination map");
        }
        if (request.beforePlayerEntry || beforeEntryAsync) {
            if (!map || map->getMapName() != mapName) {
                throw std::runtime_error("The requested destination map could not be loaded: " + mapName);
            }
            // Map loading stages its objects against the destination. Restore the complete
            // source while preparation can display a briefing; destination entry sees the
            // prepared player only after the final map swap below.
            game->setMapForResourceLoad(oldMap);
            game->getResourcesProvider()->setActiveScope(oldScope);
            if (beforeEntryAsync) {
                game.reset();
                co_await beforeEntryAsync();
                game = weakGame.lock();
            }
            if (!game || !game->getContext()->isTransitionGenerationCurrent(expectedGeneration) ||
                game->getMap() != oldMap || (oldMap && oldMap->getPlayer() != player)) {
                throw std::runtime_error("The game session changed during map transition preparation");
            }
            if (request.beforePlayerEntry) {
                request.beforePlayerEntry();
                if (!game->getContext()->isTransitionGenerationCurrent(expectedGeneration) ||
                    game->getMap() != oldMap || (oldMap && oldMap->getPlayer() != player)) {
                    throw std::runtime_error("The game session changed during map transition commit");
                }
            }
        }
        if (request.retainSourceMap && oldMap) {
            auto store = game->getContext()->getMapSessionStore();
            store->put(oldMap, request.returnAnchor);
            if (player) {
                store->setReturnCoords(oldMap->getMapName(), request.returnAnchor, player->getCoords());
            }
        }
        game->setMap(map);
        if (oldMap && game->getMap()) {
            // Transfer the existing player into the destination map without mutating the
            // source map. Detaching the player here would remove an object from the source
            // map mid-transition, which scene-manager regression tests assert must stay
            // untouched (the source map is preserved so it can be revisited). Explicit
            // targetCoords always win; otherwise a reused retained session returns to the
            // coordinate where it was left instead of replaying the destination entry tile.
            if (player) {
                game.reset();
                if (request.targetCoords) {
                    co_await map->attachPlayerAsync(player, *request.targetCoords);
                } else if (reusedSession && retainedReturnCoords) {
                    co_await map->attachPlayerAsync(player, *retainedReturnCoords);
                } else {
                    co_await map->attachPlayerAsync(player);
                }
                game = weakGame.lock();
            }
        }
        // Entry hooks may close or replace the session without throwing. Validate their result
        // before touching the active map or committing the transition.
        if (!game || !game->getContext()->isTransitionGenerationCurrent(expectedGeneration) || game->getMap() != map ||
            (player && map->getPlayer() != player)) {
            throw std::runtime_error("The game session changed during destination entry");
        }
        if (oldMap && map && request.carryTurn) {
            map->setTurn(oldMap->getTurn());
        }
        game->getContext()->advanceTransitionGeneration();
        if (CPlaytestTrace::enabled()) {
            CPlaytestTrace::addMapContext(traceFields, game->getMap());
            traceFields["result"] = "completed";
            traceFields["reusedSession"] = reusedSession;
            traceFields["transitionState"] = getTransitionStateName();
            CPlaytestTrace::record("map_transition_completed", traceFields);
        }
        resetTransition();
    } catch (...) {
        game = weakGame.lock();
        if ((!game || !game->getContext()->isActive()) && map && map != oldMap && player && map->player == player &&
            map->getObjectByName("player") == player && player->getMap() == map) {
            map->detachPlayer();
        }
        if (game && game->getContext()->isTransitionGenerationCurrent(expectedGeneration) &&
            (game->getMap() == oldMap || game->getMap() == map) && (!oldMap || oldMap->getPlayer() == player) &&
            (game->getMap() != map || !map || !map->getPlayer() || map->getPlayer() == player)) {
            if (map && map != oldMap && map->getPlayer() == player) {
                map->detachPlayer();
            }
            game->setMap(oldMap);
            game->getResourcesProvider()->setActiveScope(oldScope);
            if (player && oldMap) {
                player->setOwningMap(oldMap);
                player->relocateWithoutMoveHooks(oldCoords);
                player->setController(oldController);
                player->setFightController(oldFightController);
            }
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"result", "failed"}, {"toMap", mapName}, {"transitionState", getTransitionStateName()}};
            if (game) {
                CPlaytestTrace::addMapContext(fields, game->getMap());
            }
            CPlaytestTrace::record("map_transition_failed", fields);
        }
        resetTransition();
        completion->finish(false);
        throw;
    }
    completion->finish(true);
}

void CSceneManager::resetTransition() {
    transitionState = TransitionState::Idle;
    pendingMapName.clear();
    pendingGeneration = 0;
}
