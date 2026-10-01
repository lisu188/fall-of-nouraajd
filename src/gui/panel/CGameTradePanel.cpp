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
#include "CGameTradePanel.h"
#include "CManagementActions.h"
#include "gui/CLayout.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"
#include "gui/CDetailViewport.h"
#include "gui/CTextureCache.h"
#include "handler/CTooltipHandler.h"

#include <algorithm>
#include <map>

CListView::collection_pointer CGameTradePanel::inventoryCollection(std::shared_ptr<CGui> gui) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!player) {
        return std::make_shared<CListView::collection_type>();
    }
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(player->getItems()));
}

void CGameTradePanel::inventoryCallback(std::shared_ptr<CGui> gui, int index,
                                        std::shared_ptr<CGameObject> _newSelection) {
    inspectedItem = vstd::cast<CItem>(_newSelection);
    inspectedFromMarket = false;
    actionMessage.clear();
    detailsOffset = 0;
    updateActionAvailability(gui);
    refreshViews();
}

bool CGameTradePanel::inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    auto item = vstd::cast<CItem>(object);
    if (!item)
        return false;
    auto stack = getSellableInventoryStack(gui, item);
    return CGameObject::sameInstance(inspectedItem.lock(), item) ||
           (!stack.empty() && std::any_of(stack.begin(), stack.end(),
                                          [this](const auto &stackItem) { return isInventorySelected(stackItem); }));
}

CListView::collection_pointer CGameTradePanel::marketCollection(std::shared_ptr<CGui> gui) {
    if (!market) {
        return std::make_shared<CListView::collection_type>();
    }
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(market->getItems()));
}

void CGameTradePanel::marketCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    inspectedItem = vstd::cast<CItem>(_newSelection);
    inspectedFromMarket = true;
    actionMessage.clear();
    detailsOffset = 0;
    updateActionAvailability(gui);
    refreshViews();
}

bool CGameTradePanel::marketSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    if (!object)
        return false;
    return CGameObject::sameInstance(inspectedItem.lock(), object) ||
           std::any_of(selectedMarket.begin(), selectedMarket.end(),
                       [object](const auto &selection) { return CGameObject::sameInstance(selection.lock(), object); });
}

bool CGameTradePanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    return CGamePanel::mouseEvent(gui, type, button, x, y);
}

bool CGameTradePanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN && (i == SDLK_PAGEUP || i == SDLK_PAGEDOWN)) {
        detailsOffset = std::clamp(detailsOffset + (i == SDLK_PAGEUP ? -1 : 1) * std::max(1, detailsViewport.h - 24), 0,
                                   detailsMaximum);
        return true;
    }
    return CGamePanel::keyboardEvent(gui, type, i);
}

CGameTradePanel::CGameTradePanel() {}

void CGameTradePanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    updateActionAvailability(gui);
    CGamePanel::renderObject(gui, rect, frameTime);
}

void CGameTradePanel::updateActionAvailability(const std::shared_ptr<CGui> &gui) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    auto item = inspectedItem.lock();
    const auto saleStack = getSellableInventoryStack(gui, item);
    const bool addSale = market && player && !inspectedFromMarket &&
                         std::any_of(saleStack.begin(), saleStack.end(), [this](const auto &copy) {
                             return market->getBuyCost(copy) > 0 && !isInventorySelected(copy);
                         });
    bool addPurchase = false;
    if (market && player && inspectedFromMarket && item) {
        for (const auto &copy : market->getItems()) {
            if (copy->getTypeId() == item->getTypeId() && market->getSellCost(copy) > 0 &&
                std::none_of(selectedMarket.begin(), selectedMarket.end(),
                             [copy](const auto &selected) { return CGameObject::sameInstance(selected.lock(), copy); }))
                addPurchase = true;
        }
    }
    ManagementActions::updateButtons(
        this->ptr<CGameGraphicsObject>(),
        {{"addSelectedForSale", addSale},
         {"addSelectedForPurchase", addPurchase},
         {"clearSelection", !selectedInventory.empty() || !selectedMarket.empty()},
         {"finalizeSell", player && market && !selectedInventory.empty() && getTotalSellCost() > 0},
         {"finalizeBuy", player && market && !selectedMarket.empty() && getTotalBuyCost() > 0 &&
                             getTotalBuyCost() <= player->getGold()}});
}

bool CGameTradePanel::validatePendingTrade(std::shared_ptr<CGui> gui, bool sale, int expectedTotal) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!market || !player) {
        actionMessage = "This trade is no longer available.";
        return false;
    }
    const auto &selection = sale ? selectedInventory : selectedMarket;
    if (selection.empty()) {
        actionMessage = sale ? "Add an item to the sale first." : "Add an item to the purchase first.";
        return false;
    }
    const auto stock = market->getItems();
    for (const auto &entry : selection) {
        const auto item = entry.lock();
        if (!item || (sale ? !player->hasInInventory(item) || item->hasTag(CTag::Quest) : !stock.count(item))) {
            actionMessage = "The selected items changed. Clear the basket and select available items.";
            return false;
        }
        if ((sale ? market->getBuyCost(item) : market->getSellCost(item)) <= 0) {
            actionMessage = "The merchant cannot trade this item.";
            return false;
        }
    }
    const int currentTotal = sale ? getTotalSellCost() : getTotalBuyCost();
    if (currentTotal != expectedTotal) {
        actionMessage = "Prices changed. Review the updated total before confirming again.";
        return false;
    }
    if (!sale && currentTotal > player->getGold()) {
        actionMessage = "You need " + std::to_string(currentTotal - player->getGold()) + " more gold.";
        return false;
    }
    return true;
}

void CGameTradePanel::finalizeSell(std::shared_ptr<CGui> gui) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!market || !player) {
        return;
    }
    const auto quotedMarket = market;
    const int total = getTotalSellCost();
    if (!validatePendingTrade(gui, true, total)) {
        return;
    }
    if (!selectedInventory.empty() && gui->getGame()->getGuiHandler()->showConfirm(
                                          "Review sale",
                                          vstd::join(getItemNames(selectedInventory), "\n") +
                                              "\n\nGold after sale: " + std::to_string(player->getGold() + total),
                                          "Sell for " + std::to_string(total) + " gold", "Cancel")) {
        const auto currentMap = gui->getGame()->getMap();
        if (!currentMap || currentMap->getPlayer() != player || market != quotedMarket) {
            actionMessage = "This trade is no longer available.";
            return;
        }
        if (!validatePendingTrade(gui, true, total)) {
            return;
        }
        for (auto item : selectedInventory) {
            market->buyItem(player, item.lock());
        }
        selectedInventory.clear();
        inspectedItem.reset();
        actionMessage = "Sale completed.";
        refreshViews();
    }
}

void CGameTradePanel::finalizeBuy(std::shared_ptr<CGui> gui) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!market || !player) {
        return;
    }
    const auto quotedMarket = market;
    const int total = getTotalBuyCost();
    if (validatePendingTrade(gui, false, total)) {
        if (!selectedMarket.empty() && gui->getGame()->getGuiHandler()->showConfirm(
                                           "Review purchase",
                                           vstd::join(getItemNames(selectedMarket), "\n") +
                                               "\n\nGold after purchase: " + std::to_string(player->getGold() - total),
                                           "Buy for " + std::to_string(total) + " gold", "Cancel")) {
            const auto currentMap = gui->getGame()->getMap();
            if (!currentMap || currentMap->getPlayer() != player || market != quotedMarket) {
                actionMessage = "This trade is no longer available.";
                return;
            }
            if (!validatePendingTrade(gui, false, total)) {
                return;
            }
            for (auto item : selectedMarket) {
                market->sellItem(player, item.lock());
            }
            selectedMarket.clear();
            inspectedItem.reset();
            actionMessage = "Purchase completed.";
            refreshViews();
        }
    }
}

std::vector<std::string> CGameTradePanel::getItemNames(std::list<std::weak_ptr<CItem>> items) {
    std::map<std::string, int> counts;
    for (const auto &ob : items) {
        auto item = ob.lock();
        if (item) {
            counts[item->getLabel()]++;
        }
    }
    std::vector<std::string> names;
    for (const auto &[label, count] : counts) {
        names.push_back(count > 1 ? vstd::str(count) + "x " + label : label);
    }
    return names;
}

int CGameTradePanel::getTotalSellCost() {
    if (!market) {
        return 0;
    }
    return vstd::functional::sum<int>(selectedInventory, [this](auto item) {
        auto locked = item.lock();
        return locked ? market->getBuyCost(locked) : 0;
    });
}

int CGameTradePanel::getTotalBuyCost() {
    if (!market) {
        return 0;
    }
    return vstd::functional::sum<int>(selectedMarket, [this](auto item) {
        auto locked = item.lock();
        return locked ? market->getSellCost(locked) : 0;
    });
}

void CGameTradePanel::selectMarket(std::weak_ptr<CItem> selection) {
    if (selection.lock()) {
        auto selected = selection.lock();
        auto selectionIt = std::find_if(selectedMarket.begin(), selectedMarket.end(), [selected](const auto &item) {
            return CGameObject::sameInstance(item.lock(), selected);
        });
        if (selectionIt != selectedMarket.end()) {
            selectedMarket.erase(selectionIt);
        } else {
            selectedMarket.push_back(selection);
        }
    }
}

void CGameTradePanel::selectInventory(std::shared_ptr<CGui> gui, std::weak_ptr<CItem> selection) {
    auto selected = selection.lock();
    auto stack = getSellableInventoryStack(gui, selected);
    if (stack.empty()) {
        return;
    }

    const bool allSelected = std::all_of(stack.begin(), stack.end(),
                                         [this](const auto &stackItem) { return isInventorySelected(stackItem); });
    if (allSelected) {
        selectedInventory.remove_if([&stack](const auto &item) {
            auto selectedItem = item.lock();
            return !selectedItem || std::any_of(stack.begin(), stack.end(), [selectedItem](const auto &stackItem) {
                return CGameObject::sameInstance(selectedItem, stackItem);
            });
        });
    } else {
        selectedInventory.remove_if([](const auto &item) { return item.expired(); });
        for (const auto &stackItem : stack) {
            if (!isInventorySelected(stackItem)) {
                selectedInventory.push_back(stackItem);
            }
        }
    }
}

std::vector<std::shared_ptr<CItem>> CGameTradePanel::getSellableInventoryStack(std::shared_ptr<CGui> gui,
                                                                               std::shared_ptr<CItem> selection) {
    std::vector<std::shared_ptr<CItem>> stack;
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!player || !selection) {
        return stack;
    }
    const auto typeId = selection->getTypeId();
    for (const auto &item : player->getItems()) {
        if (item && item->getTypeId() == typeId && !item->hasTag(CTag::Quest)) {
            stack.push_back(item);
        }
    }
    return stack;
}

bool CGameTradePanel::isInventorySelected(std::shared_ptr<CItem> item) {
    return item && std::any_of(selectedInventory.begin(), selectedInventory.end(), [item](const auto &selection) {
               return CGameObject::sameInstance(selection.lock(), item);
           });
}

void CGameTradePanel::setMarket(std::shared_ptr<CMarket> _market) { market = _market; }

std::shared_ptr<CMarket> CGameTradePanel::getMarket() { return market; }

void CGameTradePanel::renderSellCost(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawText("Sale: " + vstd::str(getTotalSellCost()) + " gold\n" +
                                        std::to_string(selectedInventory.size()) +
                                        (selectedInventory.size() == 1 ? " item" : " items"),
                                    pRect);
}

void CGameTradePanel::renderBuyCost(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawText("Purchase: " + vstd::str(getTotalBuyCost()) + " gold\n" +
                                        std::to_string(selectedMarket.size()) +
                                        (selectedMarket.size() == 1 ? " item" : " items"),
                                    pRect);
}

std::string CGameTradePanel::getTradeSummary(std::shared_ptr<CGui> gui) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!player || !market) {
        return "Trading is unavailable.";
    }
    std::string text = "Your gold: " + std::to_string(player->getGold()) + "\n";
    if (!actionMessage.empty()) {
        text += actionMessage + "\n\n";
    }
    if (auto item = inspectedItem.lock()) {
        text += item->getLabel();
        text += "\n" + std::string(inspectedFromMarket ? "Buy" : "Sell") + " price: " +
                std::to_string(inspectedFromMarket ? market->getSellCost(item) : market->getBuyCost(item)) +
                " gold each";
        if (item->hasTag(CTag::Quest)) {
            text += "\nQuest item - cannot be sold.";
        }
        text += "\n";
    } else {
        text += "Select an item to inspect it.\nAdd one at a time to your sale or purchase.\n\n";
    }
    if (!selectedInventory.empty()) {
        text += "Sale total: " + std::to_string(getTotalSellCost()) + " gold (" +
                std::to_string(selectedInventory.size()) +
                (selectedInventory.size() == 1 ? " item)\nGold after sale: " : " items)\nGold after sale: ") +
                std::to_string(player->getGold() + getTotalSellCost()) + "\n";
    }
    if (!selectedMarket.empty()) {
        text += "Purchase total: " + std::to_string(getTotalBuyCost()) + " gold (" +
                std::to_string(selectedMarket.size()) + (selectedMarket.size() == 1 ? " item)\n" : " items)\n");
        if (getTotalBuyCost() <= player->getGold())
            text += "Gold after purchase: " + std::to_string(player->getGold() - getTotalBuyCost()) + "\n";
    }
    if (getTotalBuyCost() > player->getGold()) {
        text += "Need " + std::to_string(getTotalBuyCost() - player->getGold()) + " more gold for this purchase.\n";
    }
    if (!selectedInventory.empty())
        text += "\nTo sell:\n" + vstd::join(getItemNames(selectedInventory), "\n") + "\n";
    if (!selectedMarket.empty())
        text += "\nTo buy:\n" + vstd::join(getItemNames(selectedMarket), "\n") + "\n";
    if (auto item = inspectedItem.lock()) {
        auto tooltip = CTooltipHandler::buildTooltip(item);
        if (!item->getLabel().empty() && tooltip.starts_with(item->getLabel()))
            tooltip.erase(0, item->getLabel().size());
        text += "\n" + tooltip;
    }
    return text;
}

void CGameTradePanel::renderTradeSummary(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (gui && rect) {
        const auto text = getTradeSummary(gui);
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

void CGameTradePanel::addSelectedForSale(std::shared_ptr<CGui> gui) {
    if (inspectedFromMarket) {
        actionMessage = "Select an item from your bag first.";
        return;
    }
    for (const auto &item : getSellableInventoryStack(gui, inspectedItem.lock())) {
        if (!isInventorySelected(item)) {
            selectedInventory.push_back(item);
            actionMessage.clear();
            detailsOffset = 0;
            updateActionAvailability(gui);
            refreshViews();
            return;
        }
    }
    actionMessage = "No more sellable copies of this item.";
}

void CGameTradePanel::addSelectedForPurchase(std::shared_ptr<CGui> gui) {
    auto item = inspectedItem.lock();
    if (!market || !inspectedFromMarket || !item) {
        actionMessage = "Select an item from the merchant first.";
        return;
    }
    for (const auto &candidate : market->getItems()) {
        if (candidate->getTypeId() == item->getTypeId() &&
            std::none_of(selectedMarket.begin(), selectedMarket.end(), [candidate](const auto &selection) {
                return CGameObject::sameInstance(selection.lock(), candidate);
            })) {
            selectedMarket.push_back(candidate);
            actionMessage.clear();
            detailsOffset = 0;
            updateActionAvailability(gui);
            refreshViews();
            return;
        }
    }
    actionMessage = "No more copies are in stock.";
}

void CGameTradePanel::clearSelection(std::shared_ptr<CGui> gui) {
    selectedInventory.clear();
    selectedMarket.clear();
    actionMessage.clear();
    detailsOffset = 0;
    updateActionAvailability(gui);
    refreshViews();
}

bool CGameTradePanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
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
