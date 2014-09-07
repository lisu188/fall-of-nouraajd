#include "CGameScene.h"
#include "CItemSlot.h"
#include"CMap.h"
#include <QGraphicsSceneDragDropEvent>
#include <qpainter.h>
#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "Util.h"

CItemSlot::CItemSlot ( int number, std::map<int, CItem *> *equipped )
	: number ( number ), equipped ( equipped ) {
	pixmap.load ( ":/images/item.png" ); // change to slot items path in json
	pixmap = pixmap.scaled ( 50, 50,
	                         Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
	this->setAcceptDrops ( true );
}

QRectF CItemSlot::boundingRect() const {
	return QRectF ( 0, 0, 50, 50 );
}

void CItemSlot::paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
                        QWidget * ) {
	painter->drawPixmap ( 0, 0, pixmap );
}

bool CItemSlot::checkType ( int slot, QWidget *widget ) {
	if ( widget ) {
		QJsonArray config =
		    CConfigurationProvider::getConfig (
		        "config/slots.json" ).toObject()  [QString::number ( slot )].toObject() ["types"].toArray();
		for (   int i = 0; i < config.size(); i++ ) {
			if ( widget->inherits ( config[i].toString().toStdString().c_str() ) ) {
				return true;
			}
		}
	}
	return false;
}

void CItemSlot::update() {
	CItem *item = equipped->at ( number );
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
		dynamic_cast<CGameScene*> ( this->scene() )->getPlayer()->setItem ( number, ( CItem * ) event->source() );
	}
	event->acceptProposedAction();
	event->accept();
}
