#include "playerequippedview.h"
#include "item.h"
#include "CMap.h"

PlayerEquippedView::PlayerEquippedView ( std::map<int, Item *> *equipped )
	: equipped ( equipped ) {
	for ( int i = 0; i < equipped->size(); i++ ) {
		CItemSlot *slot = new CItemSlot ( i, equipped );
		slot->setParentItem ( this );
		slot->setPos ( i % 4 * CMap::getTileSize(), i / 4 * CMap::getTileSize() );
		itemSlots.push_back ( slot );
	}
	update();
}

QRectF PlayerEquippedView::boundingRect() const {
	return QRectF ( 0, 0, 4 * CMap::getTileSize(), 2 * CMap::getTileSize() );
}

void PlayerEquippedView::paint ( QPainter *painter,
                                 const QStyleOptionGraphicsItem *option,
                                 QWidget *widget ) {}

void PlayerEquippedView::update() {
	for ( std::list<CItemSlot *>::iterator it = itemSlots.begin();
	        it != itemSlots.end(); it++ ) {
		( *it )->update();
	}
	QGraphicsObject::update();
}
