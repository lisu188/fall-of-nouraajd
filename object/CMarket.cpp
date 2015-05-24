#include "CMarket.h"
#include "CMap.h"

CMarket::CMarket() {

}

CMarket::~CMarket() {

}

void CMarket::add ( std::shared_ptr<CItem> item ) {
    items.insert ( item );
}

void CMarket::remove ( std::shared_ptr<CItem> item ) {
    items.erase ( item );
}

std::set<std::shared_ptr<CItem>> CMarket::getTradeItems() {
    return items;
}

void CMarket::setItems ( QVariantList items ) {
    for ( QVariant variant:items ) {
        auto item=getMap()->createObject<CItem> ( variant.toString() );
        if ( item ) {
            add (  item );
        } else {
            qFatal ( "Object tried to put in CMarket was not a CItem" );
        }
    }
}

QVariantList CMarket::getItems() {
    return QVariantList();
}
int CMarket::getSell() const {
    return sell;
}

void CMarket::setSell ( int value ) {
    sell = value;
}
int CMarket::getBuy() const {
    return buy;
}

void CMarket::setBuy ( int value ) {
    buy = value;
}



