/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "core/CGame.h"
#include "core/CNavigation.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CSceneManager.h"
#include "core/CSerialization.h"
#include "core/CMap.h"
#include "core/CProvider.h"
#include "gui/CGui.h"
#include "gui/panel/CGamePanel.h"
#include "gui/CTooltip.h"

CGame::CGame() { CSerialization::markGameSessionStarted(); }

std::shared_ptr<CNavigationService> CGame::getNavigationService() {
    std::lock_guard resource_lock(*resourceMutex);
    std::lock_guard lock(navigationServiceMutex);
    if (context && !context->isActive())
        throw std::runtime_error("Cannot access CNavigationService after CGameContext shutdown.");
    if (!navigationService)
        navigationService = std::make_shared<CNavigationService>();
    return navigationService;
}

CGame::~CGame() {
    std::shared_ptr<CGameContext> closing_context;
    {
        std::lock_guard lock(*resourceMutex);
        closing_context = context;
    }
    if (closing_context) {
        closing_context->shutdown(this);
    }
}

void CGame::changeMap(std::string file) { CGameLoader::changeMap(this->ptr<CGame>(), std::move(file)); }

bool CGame::requestMapTransition(CMapTransitionRequest request) {
    return getSceneManager()->requestMapChange(this->ptr<CGame>(), std::move(request));
}

bool CGame::changeMapWithPreparationFlow(std::string mapName,
                                         std::move_only_function<vstd::task<void>()> beforeEntryAsync,
                                         std::function<void(bool)> completion,
                                         std::function<void()> commitBeforeEntry) {
    CMapTransitionRequest request;
    request.targetMap = std::move(mapName);
    request.onFinished = std::move(completion);
    request.beforePlayerEntry = std::move(commitBeforeEntry);
    return getSceneManager()->requestMapChange(this->ptr<CGame>(), std::move(request), std::move(beforeEntryAsync));
}

std::shared_ptr<CMap> CGame::getMap() const {
    std::lock_guard lock(*resourceMutex);
    return map;
}

void CGame::setMap(std::shared_ptr<CMap> map) {
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CGameContext> current_context;
    {
        std::lock_guard lock(*resourceMutex);
        current_context = context;
        if (current_context && !current_context->isActive() && map) {
            throw std::runtime_error("Cannot set an active map after the game session has closed");
        }
        if (this->map != map) {
            gui = _gui;
        }
    }
    if (gui) {
        auto children = gui->getChildren();
        for (const auto &child : children) {
            if (auto panel = vstd::cast<CGamePanel>(child))
                panel->close();
            else if (vstd::cast<CTooltip>(child))
                gui->removeChild(child);
        }
        gui->clearDragSession();
        gui->releasePointerCapture();
    }
    {
        std::lock_guard lock(*resourceMutex);
        current_context = context;
        if (current_context && !current_context->isActive() && map) {
            throw std::runtime_error("Cannot set an active map after the game session has closed");
        }
        this->map = map;
    }
    if (current_context && current_context->isActive()) {
        current_context->getResourcesProvider()->setActiveScope(map ? map->getMapName() : std::string());
    }
}

void CGame::setMapForResourceLoad(std::shared_ptr<CMap> map) {
    std::lock_guard lock(*resourceMutex);
    if (context && !context->isActive()) {
        this->map.reset();
        return;
    }
    this->map = std::move(map);
}

std::shared_ptr<CGameContext> CGame::getContext() {
    std::lock_guard lock(*resourceMutex);
    if (!context) {
        context = std::make_shared<CGameContext>(this->ptr<CGame>());
    }
    return context;
}

std::shared_ptr<CGuiHandler> CGame::getGuiHandler() { return getContext()->getGuiHandler(); }

std::shared_ptr<CScriptHandler> CGame::getScriptHandler() { return getContext()->getScriptHandler(); }

std::shared_ptr<CObjectHandler> CGame::getObjectHandler() { return getContext()->getObjectHandler(); }

std::shared_ptr<CSceneManager> CGame::getSceneManager() {
    std::lock_guard lock(*resourceMutex);
    if (!sceneManager) {
        sceneManager = std::make_shared<CSceneManager>();
    }
    return sceneManager;
}

std::shared_ptr<CGui> CGame::getGui() const {
    std::lock_guard lock(*resourceMutex);
    return _gui;
}

void CGame::setGui(std::shared_ptr<CGui> _gui) {
    auto current_context = getContext();
    std::lock_guard lock(*resourceMutex);
    if (_gui && !current_context->isActive()) {
        throw std::runtime_error("Cannot set an active GUI after the game session has closed");
    }
    CGame::_gui = std::move(_gui);
}

std::shared_ptr<CSlotConfig> CGame::getSlotConfiguration() { return getContext()->getSlotConfiguration(); }

std::shared_ptr<CRngHandler> CGame::getRngHandler() { return getContext()->getRngHandler(); }

std::shared_ptr<CResourcesProvider> CGame::getResourcesProvider() { return getContext()->getResourcesProvider(); }

std::shared_ptr<CConfigurationProvider> CGame::getConfigurationProvider() {
    return getContext()->getConfigurationProvider();
}
