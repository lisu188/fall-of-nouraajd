/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include <unordered_set>

#include "core/CMap.h"
#include "gui/CAnimation.h"
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
} // namespace

CListView::collection_pointer CGameFightPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(
        vstd::cast<CListView::collection_type>(gui->getGame()->getMap()->getPlayer()->getInteractions()));
}

void CGameFightPanel::interactionsCallback(std::shared_ptr<CGui> gui, int index,
                                           std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CInteraction>(_newSelection);
    if (selected.lock() != newSelection &&
        newSelection->getManaCost() <= gui->getGame()->getMap()->getPlayer()->getMana()) {
        selected = newSelection;
    } else if (newSelection && selected.lock() == newSelection &&
               newSelection->getManaCost() <= gui->getGame()->getMap()->getPlayer()->getMana()) {
        finalSelected = newSelection;
    } else {
        // TODO: rethink moving selection to CListView
        selected.reset();
    }
    refreshEncounterViews();
}

bool CGameFightPanel::interactionsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return selected.lock() && selected.lock() == object;
}

CListView::collection_pointer CGameFightPanel::itemsCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(
        vstd::cast<CListView::collection_type>(gui->getGame()->getMap()->getPlayer()->getItems()));
}

void CGameFightPanel::itemsCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    if (newSelection && newSelection->hasTag(CTag::Quest)) {
        return;
    }
    if (selectedItem.lock() != newSelection) {
        selectedItem = newSelection;
    } else if (selectedItem.lock() && selectedItem.lock() == newSelection) {
        gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
        selectedItem.reset();
    }
    refreshEncounterViews();
}

bool CGameFightPanel::itemsRightClickCallback(std::shared_ptr<CGui> gui, int index,
                                              std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    if (!newSelection || newSelection->hasTag(CTag::Quest)) {
        return false;
    }
    gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
    selectedItem.reset();
    refreshViews();
    return true;
}

bool CGameFightPanel::itemsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && !object->hasTag(CTag::Quest) && selectedItem.lock() && selectedItem.lock() == object;
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
    vstd::call_later_block([self]() {
        while (self->finalSelected.lock() == nullptr) {
            auto gui = self->getGui();
            if (!gui || gui->findChild(self) == nullptr) {
                return;
            }
            if (!vstd::event_loop<>::instance()->run()) {
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

std::shared_ptr<CCreature> CGameFightPanel::getEnemy() { return enemy.lock(); }

void CGameFightPanel::setEnemy(std::shared_ptr<CCreature> en) {
    if (en && en->isAlive() && std::find(enemies.begin(), enemies.end(), en) == enemies.end()) {
        enemies.push_back(en);
    }
    enemy = en && en->isAlive() ? en : nullptr;
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
    auto current_it = std::find(enemies.begin(), enemies.end(), current);
    enemy =
        current_it != enemies.end() ? *current_it : (enemies.empty() ? std::shared_ptr<CCreature>() : enemies.front());
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
    return object && enemy.lock() && enemy.lock() == object;
}
