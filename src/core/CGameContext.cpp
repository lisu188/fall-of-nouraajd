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
#include "core/CGame.h"
#include "core/CProvider.h"
#include "handler/CGuiHandler.h"
#include "handler/CObjectHandler.h"
#include "handler/CRngHandler.h"
#include "handler/CScriptHandler.h"

#include <atomic>
#include <stdexcept>
#include <utility>

CGameContext::CGameContext(std::shared_ptr<CGame> game) : game(std::move(game)) {}

std::shared_ptr<CObjectHandler> CGameContext::getObjectHandler() {
    if (!objectHandler) {
        objectHandler = std::make_shared<CObjectHandler>();
    }
    return objectHandler;
}

std::shared_ptr<CGuiHandler> CGameContext::getGuiHandler() {
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
    if (!scriptHandler) {
        scriptHandler = std::make_shared<CScriptHandler>();
    }
    return scriptHandler;
}

std::shared_ptr<CRngHandler> CGameContext::getRngHandler() {
    if (!rngHandler) {
        auto owner = game.lock();
        if (!owner) {
            throw std::runtime_error("Cannot create CRngHandler without an active CGame.");
        }
        rngHandler = std::make_shared<CRngHandler>(owner);
    }
    return rngHandler;
}

std::shared_ptr<CResourcesProvider> CGameContext::getResourcesProvider() {
    if (!resourcesProvider) {
        resourcesProvider = std::make_shared<CResourcesProvider>();
    }
    return resourcesProvider;
}

std::shared_ptr<CConfigurationProvider> CGameContext::getConfigurationProvider() {
    if (!configurationProvider) {
        configurationProvider = std::shared_ptr<CConfigurationProvider>(new CConfigurationProvider(),
                                                                        &CGameContext::deleteConfigurationProvider);
    }
    return configurationProvider;
}

void CGameContext::deleteConfigurationProvider(CConfigurationProvider *provider) { delete provider; }

CGameContext::TransitionGeneration CGameContext::getTransitionGeneration() const {
    return transitionGeneration.load(std::memory_order_acquire);
}

CGameContext::TransitionGeneration CGameContext::captureTransitionGeneration() const {
    return getTransitionGeneration();
}

bool CGameContext::isTransitionGenerationCurrent(TransitionGeneration expectedGeneration) const {
    return getTransitionGeneration() == expectedGeneration;
}

CGameContext::TransitionGeneration CGameContext::advanceTransitionGeneration() {
    return transitionGeneration.fetch_add(1, std::memory_order_acq_rel) + 1;
}
