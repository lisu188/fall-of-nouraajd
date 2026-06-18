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
#include "CMarket.h"
#include "core/CMap.h"
#include "object/CCreature.h"

#include <algorithm>
#include <cmath>

namespace {

constexpr int MAX_MARKET_SELL_PRICE = 100000;
constexpr int MAX_MARKET_BUYBACK_PRICE = 5000;

int boundedMarketCost(std::shared_ptr<CItem> item, int percent, int max_price) {
    if (!item || percent <= 0 || max_price <= 0) {
        return 0;
    }

    const double base_price = std::pow(2.0, static_cast<double>(item->getPower())) * 200.0;
    if (!std::isfinite(base_price)) {
        return max_price;
    }
    if (base_price <= 0.0) {
        return 0;
    }

    const double scaled_price = base_price * static_cast<double>(percent) / 100.0;
    if (!std::isfinite(scaled_price)) {
        return max_price;
    }
    if (scaled_price >= static_cast<double>(max_price)) {
        return max_price;
    }
    if (scaled_price < 1.0) {
        return 1;
    }
    return std::clamp(static_cast<int>(scaled_price), 1, max_price);
}

} // namespace

CMarket::CMarket() {}

CMarket::~CMarket() {}

void CMarket::add(std::shared_ptr<CItem> item) {
    if (!item) {
        vstd::logger::warning("Skipping null market item");
        return;
    }
    items.insert(item);
    signal("itemsChanged");
}

void CMarket::remove(std::shared_ptr<CItem> item) {
    if (items.erase(item)) {
        signal("itemsChanged");
    }
}

void CMarket::setItems(std::set<std::shared_ptr<CItem>> _items) {
    while (items.size() > 0) { // TODO: extract this to macro
        remove(*items.begin());
    }
    for (auto item : _items) {
        add(item);
    }
}

std::set<std::shared_ptr<CItem>> CMarket::getItems() { return items; }

int CMarket::getSell() const { return sell; }

void CMarket::setSell(int value) { sell = value; }

int CMarket::getBuy() const { return buy; }

void CMarket::setBuy(int value) { buy = value; }

bool CMarket::sellItem(std::shared_ptr<CCreature> cre, std::shared_ptr<CItem> item) {
    if (!cre || !item || !vstd::ctn(items, item)) {
        return false;
    }
    int price = getSellCost(item);
    if (price <= 0 || cre->getGold() < price) {
        return false;
    }
    cre->addGold(-price);
    cre->addItem(item);
    remove(item);
    return true;
}

int CMarket::getSellCost(std::shared_ptr<CItem> item) {
    if (!item) {
        return 0;
    }
    return boundedMarketCost(item, getSell(), MAX_MARKET_SELL_PRICE);
}

void CMarket::buyItem(std::shared_ptr<CCreature> cre, std::shared_ptr<CItem> item) {
    if (!cre || !item) {
        return;
    }
    int price = getBuyCost(item);
    if (price <= 0) {
        return;
    }
    std::set<std::shared_ptr<CItem>> items = cre->getInInventory();
    if (!vstd::ctn(items, item)) {
        return;
    }
    cre->addGold(price);
    add(item);
    cre->removeItem(item);
}

int CMarket::getBuyCost(std::shared_ptr<CItem> item) {
    if (!item) {
        return 0;
    }
    return std::min(boundedMarketCost(item, getBuy(), MAX_MARKET_BUYBACK_PRICE), getSellCost(item));
}
