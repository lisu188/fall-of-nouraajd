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
#include "CGameFightPanel.h"
#include <algorithm>
#include <string>
#include <unordered_set>

#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "gui/CAnimation.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"
#include "gui/object/CProxyTargetGraphicsObject.h"
#include "gui/object/CStatsGraphicsObject.h"

namespace {
void refresh_proxy_children(const std::shared_ptr<CGameGraphicsObject> &object) {
    if (!object) {
        return;
    }
    if (auto proxy = vstd::cast<CProxyTargetGraphicsObject>(object)) {
        proxy->refreshAll();
    }
    for (const auto &child : object->getChildren()) {
        refresh_proxy_children(child);
    }
}

std::shared_ptr<CMap> combat_status_map(const std::shared_ptr<CGui> &gui,
                                        const std::vector<std::shared_ptr<CCreature>> &enemies,
                                        const std::shared_ptr<CCreature> &enemy) {
    if (gui && gui->getGame() && gui->getGame()->getMap()) {
        return gui->getGame()->getMap();
    }
    if (enemy && enemy->getMap()) {
        return enemy->getMap();
    }
    for (const auto &candidate : enemies) {
        if (candidate && candidate->getMap()) {
            return candidate->getMap();
        }
    }
    return nullptr;
}

bool is_stale_combat_status(const std::string &status) {
    return status.starts_with("Combat round ") || status.find("survives the encounter") != std::string::npos ||
           status.find(" is defeated.") != std::string::npos || status.find("cancelled") != std::string::npos;
}

std::shared_ptr<CPlayer> active_player(const std::shared_ptr<CGui> &gui) {
    if (!gui || !gui->getGame() || !gui->getGame()->getMap()) {
        return nullptr;
    }
    return gui->getGame()->getMap()->getPlayer();
}

CListView::collection_pointer empty_collection() { return std::make_shared<CListView::collection_type>(); }

void clear_combat_status(const std::shared_ptr<CGui> &gui, const std::vector<std::shared_ptr<CCreature>> &enemies,
                         const std::shared_ptr<CCreature> &enemy) {
    if (auto map = combat_status_map(gui, enemies, enemy)) {
        map->setStringProperty("combatStatus", "");
    }
}

void clear_stale_combat_status(const std::shared_ptr<CGui> &gui, const std::vector<std::shared_ptr<CCreature>> &enemies,
                               const std::shared_ptr<CCreature> &enemy) {
    if (auto map = combat_status_map(gui, enemies, enemy)) {
        if (is_stale_combat_status(map->getStringProperty("combatStatus"))) {
            map->setStringProperty("combatStatus", "");
        }
    }
}
} // namespace

CListView::collection_pointer CGameFightPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
    auto player = active_player(gui);
    if (!player) {
        return empty_collection();
    }
    return std::make_shared<CListView::collection_type>(
        vstd::cast<CListView::collection_type>(player->getInteractions()));
}

void CGameFightPanel::interactionsCallback(std::shared_ptr<CGui> gui, int index,
                                           std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CInteraction>(_newSelection);
    auto player = active_player(gui);
    if (!player || !newSelection) {
        selected.reset();
    } else if (!CGameObject::sameInstance(selected.lock(), newSelection) &&
               newSelection->getManaCost() <= player->getMana()) {
        selected = newSelection;
    } else if (newSelection && CGameObject::sameInstance(selected.lock(), newSelection) &&
               newSelection->getManaCost() <= player->getMana()) {
        finalSelected = newSelection;
    } else {
        // TODO: rethink moving selection to CListView
        selected.reset();
    }
    refreshEncounterViews();
}

bool CGameFightPanel::interactionsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return selected.lock() && CGameObject::sameInstance(selected.lock(), object);
}

CListView::collection_pointer CGameFightPanel::itemsCollection(std::shared_ptr<CGui> gui) {
    auto player = active_player(gui);
    if (!player) {
        return empty_collection();
    }
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(player->getItems()));
}

void CGameFightPanel::itemsCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    auto player = active_player(gui);
    if (!player) {
        selectedItem.reset();
        refreshEncounterViews();
        return;
    }
    if (newSelection && newSelection->hasTag(CTag::Quest)) {
        return;
    }
    if (!CGameObject::sameInstance(selectedItem.lock(), newSelection)) {
        selectedItem = newSelection;
    } else if (selectedItem.lock() && CGameObject::sameInstance(selectedItem.lock(), newSelection)) {
        player->useItem(newSelection);
        selectedItem.reset();
    }
    refreshEncounterViews();
}

bool CGameFightPanel::itemsRightClickCallback(std::shared_ptr<CGui> gui, int index,
                                              std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    auto player = active_player(gui);
    if (!newSelection || newSelection->hasTag(CTag::Quest)) {
        return false;
    }
    if (!player) {
        return false;
    }
    player->useItem(newSelection);
    selectedItem.reset();
    refreshEncounterViews();
    return true;
}

bool CGameFightPanel::itemsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && !object->hasTag(CTag::Quest) && selectedItem.lock() &&
           CGameObject::sameInstance(selectedItem.lock(), object);
}

CGameFightPanel::CGameFightPanel() {}

bool CGameFightPanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_RIGHT) {
        selected.reset();
        selectedItem.reset();
        finalSelected.reset();
        refreshEncounterViews();
    }
    return true;
}

void CGameFightPanel::refreshEncounterViews() {
    refreshViews();
    refresh_proxy_children(this->ptr<CGameFightPanel>());
}

std::shared_ptr<CInteraction> CGameFightPanel::selectInteraction() {
    auto self = this->ptr<CGameFightPanel>();
    auto gui = self->getGui();
    auto game = gui ? gui->getGame() : nullptr;
    auto context = game ? game->getContext() : nullptr;
    std::weak_ptr<CMap> weakExpectedMap;
    if (game) {
        weakExpectedMap = game->getMap();
    }
    const bool hadExpectedMap = game && game->getMap() != nullptr;
    const auto expectedGeneration =
        context ? context->captureTransitionGeneration() : CGameContext::TransitionGeneration{0};
    vstd::call_later_block([self, weakExpectedMap, hadExpectedMap, context, expectedGeneration]() {
        while (self->finalSelected.lock() == nullptr) {
            if (self->isCancelled()) {
                return;
            }
            auto gui = self->getGui();
            auto game = gui ? gui->getGame() : nullptr;
            auto expectedMap = weakExpectedMap.lock();
            if ((context && !context->isTransitionGenerationCurrent(expectedGeneration)) ||
                (hadExpectedMap && (!game || !expectedMap || game->getMap() != expectedMap))) {
                self->cancel();
                return;
            }
            if (!gui || gui->findChild(self) == nullptr) {
                self->cancel();
                return;
            }
            if (SDL_HasEvent(SDL_QUIT)) {
                self->cancel();
                return;
            }
            if (!vstd::event_loop<>::instance()->run()) {
                self->cancel();
                SDL_Event quit_event;
                SDL_zero(quit_event);
                quit_event.type = SDL_QUIT;
                SDL_PushEvent(&quit_event);
                return;
            }
        }
    });
    auto ret = self->finalSelected.lock();
    self->finalSelected.reset();
    self->selected.reset();
    self->refreshEncounterViews();
    return ret;
}

bool CGameFightPanel::isCancelled() const { return cancelled; }

void CGameFightPanel::cancel() {
    cancelled = true;
    finalSelected.reset();
    selected.reset();
    selectedItem.reset();
}

void CGameFightPanel::resetCancellation() { cancelled = false; }

void CGameFightPanel::close() {
    clear_combat_status(getGui(), enemies, enemy.lock());
    cancel();
    CGamePanel::close();
}

std::shared_ptr<CCreature> CGameFightPanel::getEnemy() { return enemy.lock(); }

void CGameFightPanel::setEnemy(std::shared_ptr<CCreature> en) {
    const auto enemyIt = std::find_if(enemies.begin(), enemies.end(),
                                      [en](const auto &enemy) { return CGameObject::sameInstance(enemy, en); });
    if (en && en->isAlive() && enemyIt == enemies.end()) {
        enemies.push_back(en);
    }
    enemy = en && en->isAlive() ? en : nullptr;
    clear_stale_combat_status(getGui(), enemies, enemy.lock());
    if (enemy.lock()) {
        refreshEncounterViews();
    } else {
        refreshViews();
    }
}

void CGameFightPanel::setEnemies(const std::vector<std::shared_ptr<CCreature>> &value) {
    enemies.clear();
    std::unordered_set<std::string> names;
    for (const auto &candidate : value) {
        if (candidate && candidate->isAlive() && names.insert(candidate->getName()).second) {
            enemies.push_back(candidate);
        }
    }

    auto current = enemy.lock();
    auto current_it = std::find_if(enemies.begin(), enemies.end(), [current](const auto &candidate) {
        return CGameObject::sameInstance(candidate, current);
    });
    enemy =
        current_it != enemies.end() ? *current_it : (enemies.empty() ? std::shared_ptr<CCreature>() : enemies.front());
    clear_stale_combat_status(getGui(), enemies, enemy.lock());
    if (enemy.lock()) {
        refreshEncounterViews();
    } else {
        refreshViews();
    }
}

CListView::collection_pointer CGameFightPanel::enemiesCollection(std::shared_ptr<CGui> gui) {
    auto collection = std::make_shared<CListView::collection_type>();
    for (const auto &candidate : enemies) {
        collection->push_back(candidate);
    }
    return collection;
}

void CGameFightPanel::enemiesCallback(std::shared_ptr<CGui> gui, int index,
                                      std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CCreature>(_newSelection);
    if (newSelection && newSelection->isAlive()) {
        enemy = newSelection;
        refreshEncounterViews();
    }
}

bool CGameFightPanel::enemiesSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && enemy.lock() && CGameObject::sameInstance(enemy.lock(), object);
}

std::string CGameFightPanel::getCombatStatus(std::shared_ptr<CGui> gui) {
    if (!gui || !gui->getGame() || !gui->getGame()->getMap()) {
        return "";
    }
    auto status = gui->getGame()->getMap()->getStringProperty("combatStatus");
    if (!status.empty()) {
        return status;
    }
    if (enemy.lock()) {
        return "Choose an action.\nEnemy: " + enemy.lock()->getLabel();
    }
    return "Choose an action.";
}

void CGameFightPanel::renderCombatStatus(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    (void)frameTime;
    gui->getTextManager()->drawText(getCombatStatus(gui), rect);
}
