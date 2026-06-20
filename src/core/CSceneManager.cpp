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
#include "object/CPlayer.h"

bool CSceneManager::requestMapChange(const std::shared_ptr<CGame> &game, std::string mapName) {
    return requestMapChange(game, MapTransitionRequest{std::move(mapName)});
}

bool CSceneManager::requestMapChange(const std::shared_ptr<CGame> &game, MapTransitionRequest request) {
    const std::string mapName = std::move(request.mapName);
    if (!game) {
        if (CPlaytestTrace::enabled()) {
            CPlaytestTrace::record("map_transition_rejected", {{"reason", "missing_game"}, {"toMap", mapName}});
        }
        vstd::logger::warning("Rejected map transition without a game:", mapName);
        return false;
    }
    if (game->getSceneManager().get() != this) {
        if (CPlaytestTrace::enabled()) {
            json fields = {{"reason", "mismatched_scene_manager"}, {"toMap", mapName}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("map_transition_rejected", fields);
        }
        vstd::logger::warning("Rejected map transition for a mismatched scene manager:", mapName);
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
        return false;
    }

    transitionState = TransitionState::TransitionPending;
    pendingMapName = mapName;
    auto context = game->getContext();
    context->advanceTransitionGeneration();
    const auto expectedGeneration = context->captureTransitionGeneration();
    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"accepted", true},
            {"toMap", mapName},
            {"transitionState", getTransitionStateName()},
        };
        CPlaytestTrace::addMapContext(fields, game->getMap());
        CPlaytestTrace::record("map_transition_requested", fields);
    }

    auto manager = shared_from_this();
    std::weak_ptr<CGame> weakGame = game;
    std::weak_ptr<CGameContext> weakContext = context;
    vstd::call_later([manager, weakGame, weakContext, expectedGeneration, mapName]() {
        auto resetIfStillPending = [&manager, &mapName]() {
            if (manager->transitionState == TransitionState::TransitionPending && manager->pendingMapName == mapName) {
                manager->resetTransition();
            }
        };
        auto game = weakGame.lock();
        auto context = weakContext.lock();
        if (!game || !context || !context->isTransitionGenerationCurrent(expectedGeneration)) {
            resetIfStillPending();
            return;
        }
        if (manager->transitionState != TransitionState::TransitionPending || manager->pendingMapName != mapName) {
            return;
        }
        vstd::call_when(
            [weakGame, weakContext, expectedGeneration]() {
                auto game = weakGame.lock();
                auto context = weakContext.lock();
                return !game || !context || !context->isTransitionGenerationCurrent(expectedGeneration) ||
                       !game->getMap() || !game->getMap()->isMoving();
            },
            [manager, weakGame, weakContext, expectedGeneration, mapName]() {
                auto resetIfStillPending = [&manager, &mapName]() {
                    if (manager->transitionState == TransitionState::TransitionPending &&
                        manager->pendingMapName == mapName) {
                        manager->resetTransition();
                    }
                };
                auto game = weakGame.lock();
                auto context = weakContext.lock();
                if (!game || !context || !context->isTransitionGenerationCurrent(expectedGeneration)) {
                    resetIfStillPending();
                    return;
                }
                manager->performMapChange(game, mapName);
            });
    });
    return true;
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

void CSceneManager::performMapChange(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    try {
        transitionState = TransitionState::Transitioning;
        std::shared_ptr<CMap> oldMap = game->getMap();
        json traceFields = json::object();
        if (CPlaytestTrace::enabled()) {
            traceFields["fromMap"] = oldMap ? oldMap->getMapName() : "";
            traceFields["oldTurn"] = oldMap ? oldMap->getTurn() : 0;
            traceFields["toMap"] = mapName;
        }
        std::shared_ptr<CMap> map = CMapLoader::loadNewMap(game, mapName);
        game->setMap(map);
        if (oldMap && game->getMap()) {
            std::shared_ptr<CPlayer> player = oldMap->getPlayer();
            if (player) {
                game->getMap()->setPlayer(player);
            }
            game->getMap()->setTurn(oldMap->getTurn());
        }
        game->getContext()->advanceTransitionGeneration();
        if (CPlaytestTrace::enabled()) {
            CPlaytestTrace::addMapContext(traceFields, game->getMap());
            traceFields["result"] = "completed";
            traceFields["transitionState"] = getTransitionStateName();
            CPlaytestTrace::record("map_transition_completed", traceFields);
        }
        resetTransition();
    } catch (...) {
        if (CPlaytestTrace::enabled()) {
            json fields = {{"result", "failed"}, {"toMap", mapName}, {"transitionState", getTransitionStateName()}};
            if (game) {
                CPlaytestTrace::addMapContext(fields, game->getMap());
            }
            CPlaytestTrace::record("map_transition_failed", fields);
        }
        resetTransition();
        throw;
    }
}

void CSceneManager::resetTransition() {
    transitionState = TransitionState::Idle;
    pendingMapName.clear();
}
