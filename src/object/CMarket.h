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
#pragma once

#include "CGameObject.h"
#include <set>

class CItem;

class CCreature;

class CMarket : public CGameObject {

  V_META(CMarket, CGameObject,
         V_PROPERTY(CMarket, std::set<std::shared_ptr<CItem>>, items, getItems,
                    setItems),
         V_PROPERTY(CMarket, int, sell, getSell, setSell),
         V_PROPERTY(CMarket, int, buy, getBuy, setBuy))

public:
  CMarket();

  ~CMarket();

  void add(std::shared_ptr<CItem> item);

  void remove(std::shared_ptr<CItem> item);

  bool sellItem(std::shared_ptr<CCreature> cre, std::shared_ptr<CItem> item);

  void buyItem(std::shared_ptr<CCreature> cre, std::shared_ptr<CItem> item);

  void setItems(std::set<std::shared_ptr<CItem>> items);

  std::set<std::shared_ptr<CItem>> getItems();

  int getSell() const;

  void setSell(int value);

  int getBuy() const;

  void setBuy(int value);

  int getSellCost(std::shared_ptr<CItem> item);

  int getBuyCost(std::shared_ptr<CItem> item);

private:
  std::set<std::shared_ptr<CItem>> items;
  int sell = 100;
  int buy = 80;
};
