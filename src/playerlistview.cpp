#include "gamescene.h"
#include "playerlistview.h"

#include <qpainter.h>
#include <QWidget>
#include <QDrag>
#include <QMimeData>
#include <src/gamescene.h>

PlayerListView::PlayerListView ( std::set<CMapObject *, Comparer> *MapObjects )
	: items ( MapObjects ) {
	this->setZValue ( 3 );
	curPosition = 0;
	right = new ScrollObject ( this, true );
	left = new ScrollObject ( this, false );
	x = 4, y = 4;
	pixmap.load ( ":/images/item.png" );
	pixmap = pixmap.scaled ( CMap::getTileSize(), CMap::getTileSize(),
	                         Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
	left->setPos ( 0, y * CMap::getTileSize() );
	right->setPos ( ( x - 1 ) * CMap::getTileSize(), y * CMap::getTileSize() );
	update();
}

void PlayerListView::update() {
	if ( curPosition < 0 ) {
		curPosition = 0;
	}
	if ( items->size() - x * y < curPosition ) {
		curPosition = items->size() - x * y;
	}
	QList<QGraphicsItem *> list = childItems();
	QList<QGraphicsItem *>::Iterator childIter;
	for ( childIter = list.begin(); childIter != list.end(); childIter++ ) {
		if ( *childIter == right || *childIter == left ) {
			continue;
		}
		( *childIter )->setParentItem ( 0 );
		( *childIter )->setVisible ( false );
	}
	std::set<CMapObject *, Comparer>::iterator itemIter;
	int i = 0;
	for ( itemIter = items->begin(); itemIter != items->end(); i++, itemIter++ ) {
		CMapObject *item = *itemIter;
		if ( item->getMap() ) { //SigSegv for interaction
			item->setMap ( item->getMap()->getScene()->getPlayer()->getMap() );
		}
		item->setVisible ( false );
		item->setParentItem ( 0 );
		int position = i - curPosition;
		if ( position >= 0 && position < x * y ) {
			item->setParentItem ( this );
			item->setNumber ( position, x );
		}
	}
	right->setVisible ( items->size() > x * y );
	left->setVisible ( items->size() > x * y );
}

CMap *PlayerListView::getMap() {
	if ( items->size() ) {
		return ( *items->begin() )->getMap();
	}
	return 0;
}

void PlayerListView::setDraggable() {
	this->setFlag ( QGraphicsItem::ItemIsMovable );
}

QRectF PlayerListView::boundingRect() const {
	return QRect ( 0, 0, pixmap.size().width() * x,
	               pixmap.size().height() * ( items->size() > x * y ? y + 1 : y ) );
}

void PlayerListView::paint ( QPainter *painter,
                             const QStyleOptionGraphicsItem *option,
                             QWidget *widget ) {
	for ( int i = 0; i < x; i++ )
		for ( int j = 0; j < y; j++ ) {
			painter->drawPixmap ( i * CMap::getTileSize(), j * CMap::getTileSize(),
			                      pixmap );
		}
}

void PlayerListView::updatePosition ( int i ) {
	curPosition += i;
	update();
}

void PlayerListView::setXY ( int x, int y ) {
	this->x = x;
	this->y = y;
}
std::set<CMapObject *, Comparer> *PlayerListView::getItems() const {
	return items;
}

void PlayerListView::setItems ( std::set<CMapObject *, Comparer> *value ) {
	items = value;
	curPosition = 0;
	update();
}

void PlayerListView::dropEvent ( QGraphicsSceneDragDropEvent *event ) {
	Item *item = ( Item * ) ( event->source() );
	event->acceptProposedAction();
	item->onUse ( this->getMap()->getScene()->getPlayer() );
}
