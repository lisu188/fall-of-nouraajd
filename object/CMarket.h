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
    void add ( CItem*item );
    void remove ( CItem*item );
    std::set<CItem*> getTradeItems();
    void setItems ( QVariantList items );
    QVariantList getItems ();
    int getSell() const;
    void setSell ( int value );

    int getBuy() const;
    void setBuy ( int value );

private:
    std::set<CItem*> items;
    int sell=100;
    int buy=80;
};

