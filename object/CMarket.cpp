#include "CMarket.h"
#include "CMap.h"

CMarket::CMarket() {

}

CMarket::~CMarket() {

}

void CMarket::add ( CItem *item ) {
	items.insert ( item );
}

void CMarket::remove ( CItem *item ) {
	items.erase ( item );
}

std::set<CItem *> CMarket::getTradeItems() {
	return items;
}

void CMarket::setItems ( QVariantList items ) {
	for ( QVariant variant:items ) {
		CItem* item=getMap()->getObjectHandler()->createObject<CItem*> ( variant.toString() );
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

