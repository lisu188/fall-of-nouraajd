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
#include "CGameInventoryPanel.h"
#include "CManagementActions.h"
#include <algorithm>
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CSlotConfig.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextureCache.h"
#include "gui/CTextManager.h"
#include "gui/CDetailViewport.h"
#include "handler/CTooltipHandler.h"

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
    selectedEquipped.reset();
    selectedInventory = newSelection;
    selectedSlot.clear();
    actionMessage.clear();
    detailsOffset = 0;
    updateActionAvailability(gui);
    refreshViews();
}

bool CGameInventoryPanel::inventoryRightClickCallback(std::shared_ptr<CGui> gui, int index,
                                                      std::shared_ptr<CGameObject> _newSelection) {
    inventoryCallback(gui, index, _newSelection);
    // The animation's default right-click path opens an inspection tooltip.
    return false;
}

bool CGameInventoryPanel::inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && selectedInventory.lock() && CGameObject::sameInstance(selectedInventory.lock(), object);
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
    selectedSlot = vstd::str(index);
    selectedEquipped = newSelection;
    if (newSelection || !selectedInventory.lock()) {
        selectedInventory.reset();
    }
    actionMessage.clear();
    detailsOffset = 0;
    updateActionAvailability(gui);
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
    return ((selectedInventory.lock() &&
             gui->getGame()->getSlotConfiguration()->canFit(vstd::str(index), selectedInventory.lock())) ||
            (selectedEquipped.lock() && CGameObject::sameInstance(selectedEquipped.lock(), object)) ||
            selectedSlot == vstd::str(index));
}

CGameInventoryPanel::CGameInventoryPanel() {}

std::string CGameInventoryPanel::selectedFittingSlot(const std::shared_ptr<CGui> &gui,
                                                     const std::shared_ptr<CItem> &item) {
    auto player = inventory_player(gui);
    if (!player || !item)
        return "";
    const auto fitting = gui->getGame()->getSlotConfiguration()->getFittingSlots(item);
    if (fitting.empty())
        return "";
    if (!selectedSlot.empty())
        return fitting.count(selectedSlot) ? selectedSlot : "";
    for (const auto &candidate : fitting) {
        if (!player->getItemAtSlot(candidate))
            return candidate;
    }
    return *fitting.begin();
}

void CGameInventoryPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    updateActionAvailability(gui);
    CGamePanel::renderObject(gui, rect, frameTime);
}

void CGameInventoryPanel::updateActionAvailability(const std::shared_ptr<CGui> &gui) {
    const auto player = inventory_player(gui);
    const auto bagItem = selectedInventory.lock();
    const auto equippedItem = selectedEquipped.lock();
    const auto slot = selectedFittingSlot(gui, bagItem);
    ManagementActions::updateButtons(
        this->ptr<CGameGraphicsObject>(),
        {{"useSelected", ManagementActions::itemUseReason(player, bagItem).empty()},
         {"equipSelected", ManagementActions::equipReason(player, bagItem, slot).empty()},
         {"unequipSelected", player && equippedItem && player->hasEquipped(equippedItem) &&
                                 !equippedItem->hasTag(CTag::Quest) && !equippedItem->hasTag(CTag::Cursed)}});
}

bool CGameInventoryPanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    return CGamePanel::mouseEvent(gui, type, button, x, y);
}

std::string CGameInventoryPanel::getSelectionDetails(std::shared_ptr<CGui> gui) {
    auto player = inventory_player(gui);
    auto item = selectedInventory.lock();
    const bool inBag = item != nullptr;
    if (!item) {
        item = selectedEquipped.lock();
    }
    std::string text = actionMessage.empty() ? "" : actionMessage + "\n\n";
    if (!player || !item) {
        if (player && !selectedSlot.empty() && slot_exists(gui, selectedSlot)) {
            const auto configuration = gui->getGame()->getSlotConfiguration()->getConfiguration();
            text += CTooltipHandler::getSlotLabel(configuration.at(selectedSlot)->getSlotName());
            for (const auto &[slot, equipped] : player->getEquipped()) {
                if (equipped && slot != selectedSlot && equipped->getCoveredSlots().contains(selectedSlot)) {
                    return text + "\nOccupied by " + equipped->getLabel() +
                           ".\nRemove this compound artifact before equipping another item here.\n\n" +
                           CTooltipHandler::buildTooltip(equipped);
                }
            }
            return text + "\nEmpty slot. Select compatible equipment from your bag, then choose Equip.";
        }
        return text +
               "Select an item to inspect it.\nUse the labelled buttons to act.\nDrag equipment to a fitting slot.";
    }
    text += item->getLabel();
    text += inBag ? "\nIn your bag" : "\nEquipped";
    std::string comparison;
    auto slots = gui->getGame()->getSlotConfiguration();
    auto configuration = slots->getConfiguration();
    const auto fitting = slots->getFittingSlots(item);
    if (!fitting.empty()) {
        text += "\nFits: ";
        bool first = true;
        for (const auto &slot : fitting) {
            if (!first) {
                text += ", ";
            }
            text +=
                configuration.count(slot) ? CTooltipHandler::getSlotLabel(configuration.at(slot)->getSlotName()) : slot;
            first = false;
        }
        if (inBag) {
            auto targetSlot = fitting.count(selectedSlot) ? selectedSlot : *fitting.begin();
            if (selectedSlot.empty()) {
                for (const auto &candidate : fitting) {
                    if (!player->getItemAtSlot(candidate)) {
                        targetSlot = candidate;
                        break;
                    }
                }
            }
            auto equipped = player->getItemAtSlot(targetSlot);
            comparison += "\n\nItem bonus changes versus " + (equipped ? equipped->getLabel() : "empty slot") + ":";
            auto bonus = item->getBonus();
            auto previous = equipped ? equipped->getBonus() : nullptr;
            bool changed = false;
            if (bonus) {
                bonus->meta()->for_all_properties(bonus, [&](auto property) {
                    if (property->value_type() != std::type_index(typeid(int))) {
                        return;
                    }
                    const auto key = property->name();
                    const int difference =
                        bonus->getNumericProperty(key) - (previous ? previous->getNumericProperty(key) : 0);
                    if (difference != 0) {
                        comparison +=
                            "\n" + vstd::camel(key) + ": " + (difference > 0 ? "+" : "") + std::to_string(difference);
                        changed = true;
                    }
                });
            }
            if (!changed) {
                comparison += "\nNo numeric item bonus changes.";
            }
        }
    }
    if (item->hasTag(CTag::Quest)) {
        text += "\nQuest item - kept for your journey.";
    } else if (!inBag && item->hasTag(CTag::Cursed)) {
        text += "\nCursed - cannot be unequipped until the curse is lifted.";
    }
    if (inBag && item->hasTag(CTag::Heal) && player->getHp() >= player->getHpMax()) {
        text += "\nHealth is full.";
    }
    if (inBag && item->hasTag(CTag::Mana) && player->getMana() >= player->getManaMax()) {
        text += "\nMana is full.";
    }
    if (inBag && !fitting.empty()) {
        const auto reason = ManagementActions::equipReason(player, item, selectedFittingSlot(gui, item));
        if (!reason.empty())
            text += "\n" + reason;
    }
    text += comparison;
    auto tooltip = CTooltipHandler::buildTooltip(item);
    if (!item->getLabel().empty() && tooltip.starts_with(item->getLabel()))
        tooltip.erase(0, item->getLabel().size());
    text += "\n" + tooltip;
    return text;
}

void CGameInventoryPanel::renderSelectionDetails(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect,
                                                 int frameTime) {
    if (gui && rect) {
        const auto text = getSelectionDetails(gui);
        detailLayout.update(gui, text, rect->w);
        const int height = detailLayout.getContentHeight();
        const auto content = DetailViewport::contentRect(gui, rect, height);
        detailsViewport = *content;
        detailsMaximum = std::max(0, height - content->h);
        detailsOffset = std::clamp(detailsOffset, 0, detailsMaximum);
        detailLayout.draw(gui, content, detailsOffset);
        DetailViewport::drawScrollHint(gui, rect, content, detailsOffset, detailsMaximum);
    }
}

void CGameInventoryPanel::useSelected(std::shared_ptr<CGui> gui) {
    auto player = inventory_player(gui);
    auto item = selectedInventory.lock();
    actionMessage = ManagementActions::itemUseReason(player, item);
    if (!actionMessage.empty()) {
        return;
    }
    player->useItem(item);
    if (!player->hasInInventory(item)) {
        selectedInventory.reset();
    }
    refreshViews();
}

void CGameInventoryPanel::equipSelected(std::shared_ptr<CGui> gui) {
    auto player = inventory_player(gui);
    auto item = selectedInventory.lock();
    if (!player || !item || !player->hasInInventory(item) || item->hasTag(CTag::Quest)) {
        actionMessage = "Select equipment from your bag.";
        return;
    }
    const auto slot = selectedFittingSlot(gui, item);
    actionMessage = ManagementActions::equipReason(player, item, slot);
    if (!actionMessage.empty())
        return;
    player->equipItem(slot, item);
    if (player->getItemAtSlot(slot) == item) {
        selectedInventory.reset();
        selectedEquipped = item;
        selectedSlot = slot;
        actionMessage.clear();
        detailsOffset = 0;
    } else {
        actionMessage = "Cannot equip here. Check cursed equipment and occupied artifact slots.";
    }
    refreshViews();
}

void CGameInventoryPanel::unequipSelected(std::shared_ptr<CGui> gui) {
    auto player = inventory_player(gui);
    auto item = selectedEquipped.lock();
    if (!player || !item || item->hasTag(CTag::Quest) || item->hasTag(CTag::Cursed)) {
        actionMessage = "Select removable equipment. Quest and cursed items cannot be removed.";
        return;
    }
    auto slot = player->getSlotWithItem(item);
    if (!slot_exists(gui, slot) || player->getItemAtSlot(slot) != item) {
        selectedEquipped.reset();
        return;
    }
    player->equipItem(slot, nullptr);
    if (player->hasInInventory(item)) {
        selectedInventory = item;
        selectedEquipped.reset();
        selectedSlot.clear();
    }
    refreshViews();
}

bool CGameInventoryPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
                                          int wheelY) {
    auto origin = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : nullptr;
    SDL_Point point{x + (origin ? origin->x : 0), y + (origin ? origin->y : 0)};
    if (!SDL_PointInRect(&point, &detailsViewport)) {
        return false;
    }
    detailsOffset =
        static_cast<int>(std::clamp(static_cast<long long>(detailsOffset) - static_cast<long long>(wheelY) * 72, 0LL,
                                    static_cast<long long>(detailsMaximum)));
    return true;
}

bool CGameInventoryPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN && (key == SDLK_PAGEUP || key == SDLK_PAGEDOWN)) {
        detailsOffset = std::clamp(detailsOffset + (key == SDLK_PAGEUP ? -1 : 1) * std::max(1, detailsViewport.h - 24),
                                   0, detailsMaximum);
        return true;
    }
    return CGamePanel::keyboardEvent(gui, type, key);
}
