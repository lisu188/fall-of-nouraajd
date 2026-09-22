/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#pragma once

#include "gui/object/CWidget.h"
#include "object/CItem.h"
#include "object/CPlayer.h"

#include <map>
#include <string>

namespace ManagementActions {
inline void updateButtons(const std::shared_ptr<CGameGraphicsObject> &root,
                          const std::map<std::string, bool> &availability) {
    for (const auto &child : root->getChildren()) {
        if (auto button = vstd::cast<CWidget>(child)) {
            if (const auto found = availability.find(button->getClick()); found != availability.end())
                button->setEnabled(found->second);
        }
        updateButtons(child, availability);
    }
}

inline std::string itemUseReason(const std::shared_ptr<CPlayer> &player, const std::shared_ptr<CItem> &item) {
    if (!player || !item || !player->hasInInventory(item))
        return "Select an item from your bag.";
    if (item->hasTag(CTag::Quest))
        return "Quest item - kept for your journey.";
    const bool restoresHealth = item->hasTag(CTag::Heal);
    const bool restoresMana = item->hasTag(CTag::Mana);
    if ((restoresHealth || restoresMana) && (!restoresHealth || player->getHp() >= player->getHpMax()) &&
        (!restoresMana || player->getMana() >= player->getManaMax())) {
        return restoresHealth && restoresMana ? "Health and mana are full."
               : restoresHealth               ? "Health is full."
                                              : "Mana is full.";
    }
    return "";
}

inline std::string equipReason(const std::shared_ptr<CPlayer> &player, const std::shared_ptr<CItem> &item,
                               const std::string &slot) {
    if (!player || !item || !player->hasInInventory(item) || item->hasTag(CTag::Quest))
        return "Select equipment from your bag.";
    if (slot.empty())
        return "This item cannot be equipped.";
    auto current = player->getItemAtSlot(slot);
    if (current && current->hasTag(CTag::Cursed))
        return "The equipped item is cursed. Lift its curse before replacing it.";
    if (current && current->hasTag(CTag::Quest))
        return "Quest equipment cannot be replaced.";
    for (const auto &[otherSlot, otherItem] : player->getEquipped()) {
        if (otherItem && otherSlot != slot && otherItem->getCoveredSlots().contains(slot))
            return "This slot is occupied by a compound artifact.";
    }
    for (const auto &covered : item->getCoveredSlots()) {
        if (covered != slot && player->getItemAtSlot(covered))
            return "Remove equipment from the artifact's covered slots first.";
    }
    return "";
}
} // namespace ManagementActions
