#pragma once

#include "CGameObject.h"
#include <set>

class CItem;

class CMarket : public CGameObject {

V_META(CMarket, CGameObject,
       V_PROPERTY(CMarket, std::set<std::shared_ptr<CItem>>, items, getItems, setItems),
       V_PROPERTY(CMarket, int, sell, getSell, setSell),
       V_PROPERTY(CMarket, int, buy, getBuy, setBuy)
)

public:
    CMarket();

    ~CMarket();

    void add(std::shared_ptr<CItem> item);

    void remove(std::shared_ptr<CItem> item);

    std::set<std::shared_ptr<CItem> > getTradeItems();

    void setItems(std::set<std::shared_ptr<CItem>> items);

    std::set<std::shared_ptr<CItem>> getItems();

    int getSell() const;

    void setSell(int value);

    int getBuy() const;

    void setBuy(int value);

private:
    std::set<std::shared_ptr<CItem>> items;
    int sell = 100;
    int buy = 80;
};

GAME_PROPERTY (CMarket)
