//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#include "CGameInventoryPanel.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"
#include "core/CGame.h"
#include "core/CMap.h"

void CGameInventoryPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    drawInventory(gui, pRect, i);
    drawEquipped(gui, pRect, i);
}

void CGameInventoryPanel::drawEquipped(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr<SDL_Rect> location = std::make_shared<SDL_Rect>(*pRect.get());//this a clone, do not remove
    location->x += 600;

    equippedView->drawCollection(gui, location, frameTime);
}

void CGameInventoryPanel::drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    inventoryView->drawCollection(gui, pRect, frameTime);
}

void CGameInventoryPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {

}


CGameInventoryPanel::CGameInventoryPanel() {
    inventoryView = std::make_shared<
            CListView<
                    std::set<
                            std::shared_ptr<
                                    CItem>>>>(
            xInv, yInv, 50, true, selectionBarThickness)->withCollection(
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getInInventory();
            })->withCallback(
            [this](std::shared_ptr<CGui> gui, int index, auto newSelection) {
                if (selectedInventory.lock() != newSelection) {
                    selectedInventory = newSelection;
                } else if (selectedInventory.lock() && selectedInventory.lock() == newSelection) {
                    gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
                    selectedInventory.reset();
                }
            })->withSelect(
            [this](std::shared_ptr<CGui> gui, int index, auto object) {
                return selectedInventory.lock() && selectedInventory.lock() == object;
            });

    equippedView = std::make_shared<
            CListView<CItemMap>>(
            4, 2, 50, false, selectionBarThickness)->withCollection(
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getEquipped();
            })->withIndex(
            [](auto ob, int prevIndex) {
                return vstd::to_int(ob.first).first;
            })->withCallback(
            [this](std::shared_ptr<CGui> gui, int index, auto newSelection) {
                std::string slotName = vstd::str(index);
                if (selectedEquipped.lock()) {
                    gui->getGame()->getMap()->getPlayer()->equipItem(slotName, nullptr);
                    selectedEquipped.reset();
                } else if (selectedInventory.lock() &&
                           gui->getGame()->getSlotConfiguration()->canFit(slotName, selectedInventory.lock())) {
                    gui->getGame()->getMap()->getPlayer()->equipItem(slotName, selectedInventory.lock());
                    selectedInventory.reset();
                } else {
                    selectedEquipped = newSelection.second;
                }
            })->withSelect([this](std::shared_ptr<CGui> gui, int index, auto object) {
        return (selectedInventory.lock() &&
                gui->getGame()->getSlotConfiguration()->canFit(vstd::str(index),
                                                               selectedInventory.lock())) ||
               (selectedEquipped.lock() && selectedEquipped.lock() == object.second);
    })->withDraw(
            [](auto gui, auto item, auto loc, auto frameTime) {
                item.second->getAnimationObject()->render(gui, loc, frameTime);
            });
}

void CGameInventoryPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    if (isInInventory(gui, x, y)) {
        handleInventoryClick(gui, x, y);
    } else if (isInEquipped(gui, x, y)) {
        handleEquippedClick(gui, x, y);
    }
}

void CGameInventoryPanel::handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y) {
    inventoryView->onClicked(gui, x, y);
}

void CGameInventoryPanel::handleEquippedClick(std::shared_ptr<CGui> gui, int x, int y) {
    equippedView->onClicked(gui, x - 600, y);

}

bool CGameInventoryPanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return x < gui->getTileSize() * xInv && y < gui->getTileSize() * yInv && !isInEquipped(gui, x, y);
}

bool CGameInventoryPanel::isInEquipped(std::shared_ptr<CGui> gui, int x, int y) {
    return x >= getXSize() - gui->getTileSize() * xInv && y < gui->getTileSize() * yInv && !isInInventory(gui, x, y);
}

int CGameInventoryPanel::getXInv() {
    return xInv;
}

void CGameInventoryPanel::setXInv(int xInv) {
    CGameInventoryPanel::xInv = xInv;
}

int CGameInventoryPanel::getYInv() {
    return yInv;
}

void CGameInventoryPanel::setYInv(int yInv) {
    CGameInventoryPanel::yInv = yInv;
}

int CGameInventoryPanel::getSelectionBarThickness() {
    return selectionBarThickness;
}

void CGameInventoryPanel::setSelectionBarThickness(int selectionBarThickness) {
    CGameInventoryPanel::selectionBarThickness = selectionBarThickness;
}

