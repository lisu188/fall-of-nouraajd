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
#include "core/CGameContext.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CSceneManager.h"
#include "core/CSlotConfig.h"
#include "gui/CGui.h"
#include "handler/CGuiHandler.h"
#include "handler/CObjectHandler.h"
#include "handler/CRngHandler.h"
#include "handler/CScriptHandler.h"

#include <atomic>
#include <stdexcept>
#include <utility>

CGameContext::CGameContext(std::shared_ptr<CGame> game) : game(std::move(game)) {}

std::shared_ptr<CObjectHandler> CGameContext::getObjectHandler() {
    requireActiveService("CObjectHandler");
    if (!objectHandler) {
        objectHandler = std::make_shared<CObjectHandler>();
    }
    return objectHandler;
}

std::shared_ptr<CGuiHandler> CGameContext::getGuiHandler() {
    requireActiveService("CGuiHandler");
    if (!guiHandler) {
        auto owner = game.lock();
        if (!owner) {
            throw std::runtime_error("Cannot create CGuiHandler without an active CGame.");
        }
        guiHandler = std::make_shared<CGuiHandler>(owner);
    }
    return guiHandler;
}

std::shared_ptr<CScriptHandler> CGameContext::getScriptHandler() {
    requireActiveService("CScriptHandler");
    if (!scriptHandler) {
        scriptHandler = std::make_shared<CScriptHandler>();
    }
    return scriptHandler;
}

std::shared_ptr<CRngHandler> CGameContext::getRngHandler() {
    requireActiveService("CRngHandler");
    if (!rngHandler) {
        auto owner = game.lock();
        if (!owner) {
            throw std::runtime_error("Cannot create CRngHandler without an active CGame.");
        }
        rngHandler = std::make_shared<CRngHandler>(owner);
    }
    return rngHandler;
}

std::shared_ptr<CSlotConfig> CGameContext::getSlotConfiguration() {
    requireActiveService("CSlotConfig");
    return slotConfiguration.get([this]() {
        auto owner = game.lock();
        if (!owner) {
            throw std::runtime_error("Cannot create CSlotConfig without an active CGame.");
        }
        return owner->createObject<CSlotConfig>("slotConfiguration");
    });
}

bool CGameContext::isActive() const { return active.load(std::memory_order_acquire); }

void CGameContext::shutdown() {
    auto owner = game.lock();
    shutdown(owner.get());
}

void CGameContext::shutdown(CGame *owner) {
    if (!active.exchange(false, std::memory_order_acq_rel)) {
        return;
    }

    advanceTransitionGeneration();
    if (owner) {
        if (owner->sceneManager) {
            owner->sceneManager->resetTransition();
        }
        if (owner->_gui) {
            owner->_gui->shutdown();
            owner->_gui.reset();
        }
        owner->map.reset();
    }
    performance_guard::clearTargetFlowCache();
    if (scriptHandler) {
        scriptHandler->releaseState();
    }
    slotConfiguration.clear();
    scriptHandler.reset();
    guiHandler.reset();
    rngHandler.reset();
    objectHandler.reset();
}

CGameContext::TransitionGeneration CGameContext::getTransitionGeneration() const {
    return transitionGeneration.load(std::memory_order_acquire);
}

CGameContext::TransitionGeneration CGameContext::captureTransitionGeneration() const {
    return getTransitionGeneration();
}

bool CGameContext::isTransitionGenerationCurrent(TransitionGeneration expectedGeneration) const {
    return isActive() && getTransitionGeneration() == expectedGeneration;
}

CGameContext::TransitionGeneration CGameContext::advanceTransitionGeneration() {
    return transitionGeneration.fetch_add(1, std::memory_order_acq_rel) + 1;
}

void CGameContext::requireActiveService(const char *serviceName) const {
    if (!isActive()) {
        throw std::runtime_error(std::string("Cannot access ") + serviceName + " after CGameContext shutdown.");
    }
}
