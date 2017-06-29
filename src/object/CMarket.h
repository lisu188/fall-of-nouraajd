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

