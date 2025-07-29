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
#include "CGameInventoryPanel.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"

CListView::collection_pointer
CGameInventoryPanel::inventoryCollection(std::shared_ptr<CGui> gui) {
  return std::make_shared<CListView::collection_type>(
      vstd::cast<CListView::collection_type>(
          gui->getGame()->getMap()->getPlayer()->getItems()));
}

void CGameInventoryPanel::inventoryCallback(
    std::shared_ptr<CGui> gui, int index,
    std::shared_ptr<CGameObject> _newSelection) {
  auto newSelection = vstd::cast<CItem>(_newSelection);
  if (selectedInventory.lock() != newSelection) {
    selectedInventory = newSelection;
  } else if (selectedInventory.lock() &&
             selectedInventory.lock() == newSelection) {
    gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
    selectedInventory.reset();
  } else if (selectedInventory.lock() == nullptr &&
             selectedEquipped.lock() != nullptr) {
    gui->getGame()->getMap()->getPlayer()->equipItem(
        gui->getGame()->getMap()->getPlayer()->getSlotWithItem(
            selectedEquipped.lock()),
        nullptr);
    selectedEquipped.reset();
  }
  refreshViews();
}

bool CGameInventoryPanel::inventorySelect(std::shared_ptr<CGui> gui, int index,
                                          std::shared_ptr<CGameObject> object) {
  return selectedInventory.lock() && selectedInventory.lock() == object;
}

CListView::collection_pointer
CGameInventoryPanel::equippedCollection(std::shared_ptr<CGui> gui) {
  CListView::collection_pointer ret =
      std::make_shared<CListView::collection_type>();
  auto map = gui->getGame()->getMap()->getPlayer()->getEquipped();
  for (unsigned int i = 0;
       i < gui->getGame()->getSlotConfiguration()->getConfiguration().size();
       i++) {
    if (vstd::ctn(map, vstd::str(i))) {
      (*ret).insert(map.at(vstd::str(i)));
    } else {
      (*ret).insert(nullptr);
    }
  }
  return ret;
}

void CGameInventoryPanel::equippedCallback(
    std::shared_ptr<CGui> gui, int index,
    std::shared_ptr<CGameObject> _newSelection) {
  auto newSelection = vstd::cast<CItem>(_newSelection);
  std::string slotName = vstd::str(index);
  if (selectedEquipped.lock()) {
    gui->getGame()->getMap()->getPlayer()->equipItem(slotName, nullptr);
    selectedEquipped.reset();
  } else if (selectedInventory.lock() &&
             gui->getGame()->getSlotConfiguration()->canFit(
                 slotName, selectedInventory.lock())) {
    gui->getGame()->getMap()->getPlayer()->equipItem(slotName,
                                                     selectedInventory.lock());
    selectedInventory.reset();
  } else {
    selectedEquipped = newSelection;
  }
  refreshViews();
}

bool CGameInventoryPanel::equippedSelect(std::shared_ptr<CGui> gui, int index,
                                         std::shared_ptr<CGameObject> object) {
  return (selectedInventory.lock() &&
          gui->getGame()->getSlotConfiguration()->canFit(
              vstd::str(index), selectedInventory.lock())) ||
         (selectedEquipped.lock() && selectedEquipped.lock() == object);
}

CGameInventoryPanel::CGameInventoryPanel() {}
