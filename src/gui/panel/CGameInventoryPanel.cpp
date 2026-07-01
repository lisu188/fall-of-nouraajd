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
#include "core/CSlotConfig.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextureCache.h"

namespace {
constexpr const char *INVENTORY_COLLECTION = "inventoryCollection";
constexpr const char *EQUIPPED_COLLECTION = "equippedCollection";

std::shared_ptr<CPlayer> inventory_player(const std::shared_ptr<CGui> &gui) {
    if (!gui || !gui->getGame() || !gui->getGame()->getMap()) {
        return nullptr;
    }
    return gui->getGame()->getMap()->getPlayer();
}

std::shared_ptr<CItem> usable_item(std::shared_ptr<CGameObject> object) {
    auto item = vstd::cast<CItem>(object);
    if (!item || item->hasTag(CTag::Quest)) {
        return nullptr;
    }
    return item;
}

std::shared_ptr<CListView> drag_source_list(const std::shared_ptr<CGui> &gui) {
    if (!gui || !gui->hasDragSession()) {
        return nullptr;
    }
    return vstd::cast<CListView>(gui->getDragSession()->sourceWidget.lock());
}

bool drag_source_collection_is(const std::shared_ptr<CGui> &gui, const std::string &collection) {
    auto source = drag_source_list(gui);
    return source && source->getCollection() == collection;
}

std::shared_ptr<CItem> drag_payload_item(const std::shared_ptr<CGui> &gui) {
    if (!gui || !gui->hasDragSession()) {
        return nullptr;
    }
    return usable_item(gui->getDragSession()->payload);
}

bool slot_exists(const std::shared_ptr<CGui> &gui, const std::string &slotName) {
    if (!gui || !gui->getGame()) {
        return false;
    }
    auto configuration = gui->getGame()->getSlotConfiguration()->getConfiguration();
    return vstd::ctn(configuration, slotName);
}

bool target_allows_drop(std::shared_ptr<CGameObject> object) {
    auto item = vstd::cast<CItem>(object);
    return !item || !item->hasTag(CTag::Quest);
}
bool drag_release_over_inventory_list(CGameInventoryPanel &panel, const std::shared_ptr<CGui> &gui) {
    if (!gui || !gui->hasDragSession()) {
        return false;
    }
    const auto *session = gui->getDragSession();
    for (const auto &child : panel.getChildren()) {
        auto list = vstd::cast<CListView>(child);
        if (!list || (list->getCollection() != INVENTORY_COLLECTION && list->getCollection() != EQUIPPED_COLLECTION)) {
            continue;
        }
        auto layout = list->getLayout();
        auto rect = layout ? layout->getRect(list) : nullptr;
        if (rect && session->current.x >= rect->x && session->current.x < rect->x + rect->w &&
            session->current.y >= rect->y && session->current.y < rect->y + rect->h) {
            return true;
        }
    }
    return false;
}
} // namespace

CListView::collection_pointer CGameInventoryPanel::inventoryCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(
        vstd::cast<CListView::collection_type>(gui->getGame()->getMap()->getPlayer()->getItems()));
}

void CGameInventoryPanel::inventoryCallback(std::shared_ptr<CGui> gui, int index,
                                            std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    if (newSelection && newSelection->hasTag(CTag::Quest)) {
        return;
    }
    if (!CGameObject::sameInstance(selectedInventory.lock(), newSelection)) {
        selectedEquipped.reset();
        selectedInventory = newSelection;
    } else if (selectedInventory.lock() && CGameObject::sameInstance(selectedInventory.lock(), newSelection)) {
        gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
        selectedInventory.reset();
    } else if (selectedInventory.lock() == nullptr && selectedEquipped.lock() != nullptr) {
        gui->getGame()->getMap()->getPlayer()->equipItem(
            gui->getGame()->getMap()->getPlayer()->getSlotWithItem(selectedEquipped.lock()), nullptr);
        selectedEquipped.reset();
    }
    refreshViews();
}

bool CGameInventoryPanel::inventoryRightClickCallback(std::shared_ptr<CGui> gui, int index,
                                                      std::shared_ptr<CGameObject> _newSelection) {
    auto item = usable_item(_newSelection);
    auto player = inventory_player(gui);
    if (!player || !item || !player->hasInInventory(item)) {
        // Empty cell, non-item, quest item, or an item that no longer belongs to the
        // player: reset any pending selection and let parents keep processing the click.
        selectedEquipped.reset();
        selectedInventory.reset();
        refreshViews();
        return false;
    }
    // Delegate use semantics (heal/mana full-resource guards, disposable consumption)
    // to CCreature::useItem(); the GUI must not duplicate that logic.
    player->useItem(item);
    selectedEquipped.reset();
    selectedInventory.reset();
    refreshViews();
    return true;
}

bool CGameInventoryPanel::inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && !object->hasTag(CTag::Quest) && selectedInventory.lock() &&
           CGameObject::sameInstance(selectedInventory.lock(), object);
}

bool CGameInventoryPanel::inventoryDragStart(std::shared_ptr<CGui> gui, int index,
                                             std::shared_ptr<CGameObject> object) {
    auto item = usable_item(object);
    auto player = inventory_player(gui);
    return player && item && player->hasInInventory(item);
}

void CGameInventoryPanel::inventoryDragCancel(std::shared_ptr<CGui> gui, int index,
                                              std::shared_ptr<CGameObject> object) {
    if (drag_release_over_inventory_list(*this, gui)) {
        return;
    }
    auto item = usable_item(object);
    auto player = inventory_player(gui);
    if (!player || !item || !player->hasInInventory(item)) {
        return;
    }
    selectedEquipped.reset();
    selectedInventory = item;
    refreshViews();
}

bool CGameInventoryPanel::inventoryDropValidate(std::shared_ptr<CGui> gui, int index,
                                                std::shared_ptr<CGameObject> object) {
    auto item = drag_payload_item(gui);
    auto player = inventory_player(gui);
    if (!player || !item || !target_allows_drop(object) || !drag_source_collection_is(gui, EQUIPPED_COLLECTION)) {
        return false;
    }
    const std::string slotName = vstd::str(gui->getDragSession()->sourceIndex);
    return slot_exists(gui, slotName) && player->getItemAtSlot(slotName) == item;
}

void CGameInventoryPanel::inventoryDrop(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    if (!inventoryDropValidate(gui, index, object)) {
        return;
    }
    auto player = inventory_player(gui);
    const std::string slotName = vstd::str(gui->getDragSession()->sourceIndex);
    player->equipItem(slotName, nullptr);
    selectedInventory.reset();
    selectedEquipped.reset();
    refreshViews();
}

CListView::collection_pointer CGameInventoryPanel::equippedCollection(std::shared_ptr<CGui> gui) {
    CListView::collection_pointer ret = std::make_shared<CListView::collection_type>();
    auto map = gui->getGame()->getMap()->getPlayer()->getEquipped();
    for (unsigned int i = 0; i < gui->getGame()->getSlotConfiguration()->getConfiguration().size(); i++) {
        if (vstd::ctn(map, vstd::str(i))) {
            (*ret).insert(map.at(vstd::str(i)));
        } else {
            (*ret).insert(nullptr);
        }
    }
    return ret;
}

void CGameInventoryPanel::equippedCallback(std::shared_ptr<CGui> gui, int index,
                                           std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    // Quest and cursed items cannot be selected out of their equipped slot: quest items
    // must not be dropped, and cursed items stay locked until the curse is lifted.
    if (newSelection && (newSelection->hasTag(CTag::Quest) || newSelection->hasTag(CTag::Cursed))) {
        return;
    }
    std::string slotName = vstd::str(index);
    if (selectedEquipped.lock()) {
        gui->getGame()->getMap()->getPlayer()->equipItem(slotName, nullptr);
        selectedEquipped.reset();
    } else if (selectedInventory.lock() &&
               gui->getGame()->getSlotConfiguration()->canFit(slotName, selectedInventory.lock())) {
        gui->getGame()->getMap()->getPlayer()->equipItem(slotName, selectedInventory.lock());
        selectedInventory.reset();
    } else {
        selectedInventory.reset();
        selectedEquipped = newSelection;
    }
    refreshViews();
}

bool CGameInventoryPanel::equippedDragStart(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    auto item = usable_item(object);
    auto player = inventory_player(gui);
    const std::string slotName = vstd::str(index);
    return player && item && slot_exists(gui, slotName) && player->getItemAtSlot(slotName) == item;
}

void CGameInventoryPanel::equippedDragCancel(std::shared_ptr<CGui> gui, int index,
                                             std::shared_ptr<CGameObject> object) {
    if (drag_release_over_inventory_list(*this, gui)) {
        return;
    }
    auto item = usable_item(object);
    auto player = inventory_player(gui);
    const std::string slotName = vstd::str(index);
    if (!player || !item || !slot_exists(gui, slotName) || player->getItemAtSlot(slotName) != item) {
        return;
    }
    selectedInventory.reset();
    selectedEquipped = item;
    refreshViews();
}

bool CGameInventoryPanel::equippedDropValidate(std::shared_ptr<CGui> gui, int index,
                                               std::shared_ptr<CGameObject> object) {
    auto item = drag_payload_item(gui);
    auto player = inventory_player(gui);
    if (!player || !item || !target_allows_drop(object) || !drag_source_collection_is(gui, INVENTORY_COLLECTION)) {
        return false;
    }
    const std::string slotName = vstd::str(index);
    auto targetItem = vstd::cast<CItem>(object);
    return slot_exists(gui, slotName) && player->hasInInventory(item) &&
           player->getItemAtSlot(slotName) == targetItem &&
           gui->getGame()->getSlotConfiguration()->canFit(slotName, item);
}

void CGameInventoryPanel::equippedDrop(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    if (!equippedDropValidate(gui, index, object)) {
        return;
    }
    auto player = inventory_player(gui);
    auto item = drag_payload_item(gui);
    player->equipItem(vstd::str(index), item);
    selectedInventory.reset();
    selectedEquipped.reset();
    refreshViews();
}

bool CGameInventoryPanel::equippedSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return (!object || !object->hasTag(CTag::Quest)) &&
           ((selectedInventory.lock() &&
             gui->getGame()->getSlotConfiguration()->canFit(vstd::str(index), selectedInventory.lock())) ||
            (selectedEquipped.lock() && CGameObject::sameInstance(selectedEquipped.lock(), object)));
}

CGameInventoryPanel::CGameInventoryPanel() {}

bool CGameInventoryPanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_RIGHT) {
        selectedInventory.reset();
        selectedEquipped.reset();
        refreshViews();
    }
    return true;
}
