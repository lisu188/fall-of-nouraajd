/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "gui/CAnimation.h"
#include "gui/CTextureCache.h"
#include "core/CMap.h"
#include "gui/object/CStatsGraphicsObject.h"

CListView::collection_pointer CGameFightPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(
            vstd::cast<CListView::collection_type>(gui->getGame()->getMap()->getPlayer()->getInteractions()));
}

void CGameFightPanel::interactionsCallback(std::shared_ptr<CGui> gui, int index,
                                           std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CInteraction>(_newSelection);
    if (selected.lock() !=
        newSelection &&
        newSelection->getManaCost() <=
        gui->getGame()->getMap()->getPlayer()->getMana()) {
        selected = newSelection;
    } else if (
            selected.lock() ==
            newSelection &&
            newSelection->getManaCost() <=
            gui->getGame()->getMap()->getPlayer()->getMana()) {
        finalSelected = newSelection;
    } else {
        //TODO: rethink moving selection to CListView
        selected.reset();
    }
    refreshViews();
}

bool CGameFightPanel::interactionsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return selected.lock() && selected.lock() == object;
}

CListView::collection_pointer CGameFightPanel::itemsCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(
            gui->getGame()->getMap()->getPlayer()->getItems()));
}

void CGameFightPanel::itemsCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    if (selectedItem.lock() != newSelection) {
        selectedItem = newSelection;
    } else if (selectedItem.lock() && selectedItem.lock() == newSelection) {
        gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
        selectedItem.reset();
    }
    refreshViews();
}

bool CGameFightPanel::itemsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return selectedItem.lock() && selectedItem.lock() == object;
}

CGameFightPanel::CGameFightPanel() {

}

std::shared_ptr<CInteraction> CGameFightPanel::selectInteraction() {
    vstd::wait_until([this]() {
        return finalSelected.lock() != nullptr;
    });
    auto ret = finalSelected.lock();
    finalSelected.reset();
    selected.reset();
    refreshViews();
    return ret;
}

std::shared_ptr<CCreature> CGameFightPanel::getEnemy() {
    return enemy.lock();
}

void CGameFightPanel::setEnemy(std::shared_ptr<CCreature> en) {
    enemy = en;
}

void CGameFightPanel::drawEnemy(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
//    int size = gui->getTileSize() * 4;
//    std::shared_ptr<SDL_Rect> loc = RECT(
//            pRect->x + (getWidth() / 2 - size / 2),
//            pRect->y + ((getHeight() - gui->getTileSize()) / 2 - size / 2),
//            size,
//            size);
//    enemy.lock()->getGraphicsObject()->renderObject(gui, loc, frameTime);
//
//    CStatsGraphicsUtil::drawStats(gui, enemy.lock(), loc->x, loc->y + loc->h, loc->w, loc->h / 4.0, false, false);
}
