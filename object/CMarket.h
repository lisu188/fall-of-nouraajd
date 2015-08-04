#pragma once
#include "CGameObject.h"
#include <set>
class CItem;
class CMarket : public CGameObject {
    Q_OBJECT
    Q_PROPERTY ( QVariantList items READ getItems WRITE setItems USER true )
    Q_PROPERTY ( int sell READ getSell WRITE setSell USER true )
    Q_PROPERTY ( int buy READ getBuy WRITE setBuy USER true )
public:
    CMarket();
    ~CMarket();
    void add ( std::shared_ptr<CItem> item );
    void remove ( std::shared_ptr<CItem> item );
    std::set<std::shared_ptr<CItem> > getTradeItems();
    void setItems ( QVariantList items );
    QVariantList getItems ();
    int getSell() const;
    void setSell ( int value );

    int getBuy() const;
    void setBuy ( int value );

private:
    std::set<std::shared_ptr<CItem>> items;
    int sell=100;
    int buy=80;
};
GAME_PROPERTY ( CMarket )
