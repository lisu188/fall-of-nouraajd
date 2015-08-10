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

void CMarket::setItems ( std::set<std::shared_ptr<CItem>> items ) {
    this->items=items;
}

std::set<std::shared_ptr<CItem>> CMarket::getItems() {
    return items;
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



