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
#include "CGameInventoryPanel.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"
#include "core/CGame.h"
#include "core/CMap.h"


vstd::list<std::shared_ptr<CGameObject>> CGameInventoryPanel::inventoryCollection(std::shared_ptr<CGui> gui) {
    return vstd::cast<vstd::list<std::shared_ptr<CGameObject>>>(
            gui->getGame()->getMap()->getPlayer()->getItems());
}

void CGameInventoryPanel::inventoryCallback(std::shared_ptr<CGui> gui, int index,
                                            std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    if (selectedInventory.lock() != newSelection) {
        selectedInventory = newSelection;
    } else if (selectedInventory.lock() && selectedInventory.lock() == newSelection) {
        gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
        selectedInventory.reset();
    }
}

bool CGameInventoryPanel::inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return selectedInventory.lock() && selectedInventory.lock() == object;
}

vstd::list<std::shared_ptr<CGameObject>> CGameInventoryPanel::equippedCollection(std::shared_ptr<CGui> gui) {
    vstd::list<std::shared_ptr<CGameObject>> ret;
    auto map = gui->getGame()->getMap()->getPlayer()->getEquipped();
    for (int i = 0; i < gui->getGame()->getSlotConfiguration()->getConfiguration().size(); i++) {
        if (vstd::ctn(map, vstd::str(i))) {
            ret.insert(map.at(vstd::str(i)));
        } else {
            ret.insert(nullptr);
        }

    }
    return ret;
}

void CGameInventoryPanel::equippedCallback(std::shared_ptr<CGui> gui, int index,
                                           std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    std::string slotName = vstd::str(index);
    if (selectedEquipped.lock()) {
        gui->getGame()->getMap()->getPlayer()->equipItem(slotName, nullptr);
        selectedEquipped.reset();
    } else if (selectedInventory.lock() &&
               gui->getGame()->getSlotConfiguration()->canFit(slotName, selectedInventory.lock())) {
        gui->getGame()->getMap()->getPlayer()->equipItem(slotName, selectedInventory.lock());
        selectedInventory.reset();
    } else {
        selectedEquipped = newSelection;
    }
}

bool CGameInventoryPanel::equippedSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return (selectedInventory.lock() &&
            gui->getGame()->getSlotConfiguration()->canFit(vstd::str(index),
                                                           selectedInventory.lock())) ||
           (selectedEquipped.lock() && selectedEquipped.lock() == object);
}


CGameInventoryPanel::CGameInventoryPanel() {

}
