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
#include "CMarket.h"
#include "core/CMap.h"
#include "object/CCreature.h"

CMarket::CMarket() {

}

CMarket::~CMarket() {

}

void CMarket::add(std::shared_ptr<CItem> item) {
    items.insert(item);
}

void CMarket::remove(std::shared_ptr<CItem> item) {
    items.erase(item);
}


void CMarket::setItems(std::set<std::shared_ptr<CItem>> items) {
    this->items = items;
}

std::set<std::shared_ptr<CItem>> CMarket::getItems() {
    return items;
}

int CMarket::getSell() const {
    return sell;
}

void CMarket::setSell(int value) {
    sell = value;
}

int CMarket::getBuy() const {
    return buy;
}

void CMarket::setBuy(int value) {
    buy = value;
}

bool CMarket::sellItem(std::shared_ptr<CCreature> cre, std::shared_ptr<CItem> item) {
    int price = getSellCost(item);
    vstd::fail_if(!vstd::ctn(items, item), "tried to sell item not on sell");
    if (cre->getGold() < price) {
        return false;
    }
    cre->addGold(-price);
    cre->addItem(item);
    items.erase(item);
    return true;
}

int CMarket::getSellCost(std::shared_ptr<CItem> item) {
    return (int) (pow(2, item->getPower()) * 200.0 * ((double) getSell()) / 100.0);
}

void CMarket::buyItem(std::shared_ptr<CCreature> cre, std::shared_ptr<CItem> item) {
    int price = getBuyCost(item);
    std::set<std::shared_ptr<CItem>> items = cre->getInInventory();
    vstd::fail_if(!vstd::ctn(items, item), "tried to sell not owned item");
    cre->addGold(price);
    this->items.insert(item);
    cre->removeFromInventory(item);
}

int CMarket::getBuyCost(std::shared_ptr<CItem> item) {
    return (int) (pow(2, item->getPower()) * 200.0 * ((double) getBuy()) / 100.0);
}



