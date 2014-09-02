#include "CGameScene.h"
#include "CItemSlot.h"
#include"CMap.h"
#include <QGraphicsSceneDragDropEvent>
#include <qpainter.h>
#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "util.h"

CItemSlot::CItemSlot ( int number, std::map<int, Item *> *equipped )
	: number ( number ), equipped ( equipped ) {
	pixmap.load ( ":/images/item.png" ); // change to slot items path in json
	pixmap = pixmap.scaled ( CMap::getTileSize(), CMap::getTileSize(),
	                         Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
	this->setAcceptDrops ( true );
}

QRectF CItemSlot::boundingRect() const {
	return QRectF ( 0, 0, CMap::getTileSize(), CMap::getTileSize() );
}

void CItemSlot::paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
                        QWidget * ) {
	painter->drawPixmap ( 0, 0, pixmap );
}

bool CItemSlot::checkType ( int slot, QWidget *widget ) {
	if ( widget ) {
		Json::Value config =
		    ( *CConfigurationProvider::getConfig (
		          "config/slots.json" ) ) [to_string ( slot ).c_str()]["types"];
		for ( int i = 0; i < config.size(); i++ ) {
			if ( widget->inherits ( config[i].asCString() ) ) {
				return true;
			}
		}
	}
	return false;
}

void CItemSlot::update() {
	Item *item = equipped->at ( number );
	if ( item ) {
		item->setParentItem ( this );
		item->setPos ( 0, 0 );
		item->setVisible ( true );
		item->QGraphicsItem::update();
	}
	QGraphicsObject::update();
}

void CItemSlot::dragMoveEvent ( QGraphicsSceneDragDropEvent *event ) {
	QGraphicsObject::dragMoveEvent ( event );
	event->setAccepted ( checkType ( number, event->source() ) );
}

void CItemSlot::dropEvent ( QGraphicsSceneDragDropEvent *event ) {
	QGraphicsObject::dropEvent ( event );
	if ( checkType ( number, event->source() ) ) {
		dynamic_cast<CGameScene*> ( this->scene() )->getPlayer()->setItem ( number, ( Item * ) event->source() );
	}
	event->acceptProposedAction();
	event->accept();
}
