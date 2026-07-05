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
#include "CGameTradePanel.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"

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
    this->selectInventory(gui, vstd::cast<CItem>(_newSelection));
    refreshViews();
}

bool CGameTradePanel::inventorySelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    auto item = vstd::cast<CItem>(object);
    auto stack = getSellableInventoryStack(gui, item);
    return !stack.empty() && std::all_of(stack.begin(), stack.end(),
                                         [this](const auto &stackItem) { return isInventorySelected(stackItem); });
}

CListView::collection_pointer CGameTradePanel::marketCollection(std::shared_ptr<CGui> gui) {
    if (!market) {
        return std::make_shared<CListView::collection_type>();
    }
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(market->getItems()));
}

void CGameTradePanel::marketCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    this->selectMarket(vstd::cast<CItem>(_newSelection));
    refreshViews();
}

bool CGameTradePanel::marketSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return std::any_of(selectedMarket.begin(), selectedMarket.end(),
                       [object](const auto &selection) { return CGameObject::sameInstance(selection.lock(), object); });
}

bool CGameTradePanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_RIGHT) {
        selectedInventory.clear();
        selectedMarket.clear();
        refreshViews();
    }
    return true;
}

bool CGameTradePanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        // TODO: get rid of this
        if (i == SDLK_SPACE) {
            close();
        }
    }
    return true;
}

CGameTradePanel::CGameTradePanel() {}

void CGameTradePanel::finalizeSell(std::shared_ptr<CGui> gui) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!market || !player) {
        return;
    }
    if (!selectedInventory.empty() &&
        gui->getGame()->getGuiHandler()->showQuestion("Do You want to sell these items: " +
                                                      vstd::join(getItemNames(selectedInventory), ", "))) {
        for (auto item : selectedInventory) {
            market->buyItem(player, item.lock());
        }
        selectedInventory.clear();
    }
}

void CGameTradePanel::finalizeBuy(std::shared_ptr<CGui> gui) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!market || !player) {
        return;
    }
    if (getTotalBuyCost() > player->getGold()) {
        gui->getGame()->getGuiHandler()->showInfo("You cannot afford all selected items!");
    } else {
        if (!selectedMarket.empty() &&
            gui->getGame()->getGuiHandler()->showQuestion("Do You want to buy these items: " +
                                                          vstd::join(getItemNames(selectedMarket), ", "))) {
            for (auto item : selectedMarket) {
                market->sellItem(player, item.lock());
            }
            selectedMarket.clear();
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
    gui->getTextManager()->drawTextCentered(vstd::str(getTotalSellCost()), pRect);
}

void CGameTradePanel::renderBuyCost(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawTextCentered(vstd::str(getTotalBuyCost()), pRect);
}
