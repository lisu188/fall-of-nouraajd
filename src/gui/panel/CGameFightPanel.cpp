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

void CGameFightPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    drawInteractions(gui, pRect, i);
    drawEnemy(gui, pRect, i);
}

void CGameFightPanel::drawInteractions(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr<SDL_Rect> location = std::make_shared<SDL_Rect>(*pRect.get());//cloning, do not remove
    location->y += (getWidth() - gui->getTileSize());

    interactionsView->drawCollection(gui,
                                     location,
                                     frameTime);

    location->y -= gui->getTileSize();

    itemsView->drawCollection(gui,
                              location,
                              frameTime);
}


CGameFightPanel::CGameFightPanel() {
    interactionsView = std::make_shared<CListView<std::set<
            std::shared_ptr<
                    CInteraction>>>>(
            getWidth() / tileSize, 1, tileSize, true, selectionBarThickness)->withCollection(
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getInteractions();
            })->withCallback(
            [this](std::shared_ptr<CGui> gui, int index,
                   auto newSelection) {
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
            })->withSelect(
            [this](std::shared_ptr<CGui> gui, int index, auto object) {
                return selected.lock() && selected.lock() == object;
            });

    itemsView = std::make_shared<CListView<std::set<
            std::shared_ptr<
                    CItem>>>>(getWidth() / tileSize, 1, tileSize, true, selectionBarThickness)->withCollection(
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getItems();
            })->withCallback(
            [this](std::shared_ptr<CGui> gui, int index,
                   auto newSelection) {
                if (selectedItem.lock() != newSelection) {
                    selectedItem = newSelection;
                } else if (selectedItem.lock() && selectedItem.lock() == newSelection) {
                    gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
                    selectedItem.reset();
                }
            })->withSelect(
            [this](std::shared_ptr<CGui> gui, int index, auto object) {
                return selectedItem.lock() && selectedItem.lock() == object;
            });
}

void CGameFightPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    //TODO: shift values
    if (isInInteractions(gui, x, y)) {
        handleInteractionsClick(gui, x, y - getInteractionsLocation(gui));
    } else if (isInInventory(gui, x, y)) {
        handleInventoryClick(gui, x, y - getInventoryLocation(gui));
    }
}

void CGameFightPanel::handleInteractionsClick(std::shared_ptr<CGui> gui, int x, int y) {
    interactionsView->onClicked(gui, x, y);
}


void CGameFightPanel::handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y) {
    itemsView->onClicked(gui, x, y);

}

bool CGameFightPanel::isInInteractions(std::shared_ptr<CGui> gui, int x, int y) {
    return y > (getInteractionsLocation(gui)) && y < (getInteractionsLocation(gui) + tileSize);
}

int CGameFightPanel::getInteractionsLocation(std::shared_ptr<CGui> gui) { return getHeight() - gui->getTileSize(); }

//TODO: make this method strict
bool CGameFightPanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return y > getInventoryLocation(gui) && y < getInventoryLocation(gui) + tileSize;
}

int CGameFightPanel::getInventoryLocation(std::shared_ptr<CGui> gui) { return getHeight() - (gui->getTileSize() * 2); }


int CGameFightPanel::getSelectionBarThickness() {
    return selectionBarThickness;
}

void CGameFightPanel::setSelectionBarThickness(int selectionBarThickness) {
    CGameFightPanel::selectionBarThickness = selectionBarThickness;
}

std::shared_ptr<CInteraction> CGameFightPanel::selectInteraction() {
    vstd::wait_until([this]() {
        return finalSelected.lock() != nullptr;
    });
    auto ret = finalSelected.lock();
    finalSelected.reset();
    selected.reset();
    return ret;
}

std::shared_ptr<CCreature> CGameFightPanel::getEnemy() {
    return enemy.lock();
}

void CGameFightPanel::setEnemy(std::shared_ptr<CCreature> en) {
    enemy = en;
}

void CGameFightPanel::drawEnemy(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    int size = gui->getTileSize() * 4;
    std::shared_ptr<SDL_Rect> loc = RECT(
            pRect->x + (getWidth() / 2 - size / 2),
            pRect->y + ((getHeight() - gui->getTileSize()) / 2 - size / 2),
            size,
            size);
    enemy.lock()->getGraphicsObject()->render(gui, loc, frameTime);

    CStatsGraphicsUtil::drawStats(gui, enemy.lock(), loc->x, loc->y + loc->h, loc->w, loc->h / 4.0, false, false);
}
