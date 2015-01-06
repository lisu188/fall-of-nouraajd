#include "CGamePanel.h"
#include "CGameScene.h"
#include <qpainter.h>
#include <sstream>
#include <QDebug>
#include <QDrag>
#include <qpainter.h>
#include "CGameView.h"
#include "CPlayerView.h"
#include "object/CObject.h"
#include <QBitmap>
#include <QFont>
#include "handler/CHandler.h"


CCharPanel::CCharPanel() {
	setZValue ( 6 );
	setVisible ( false );
}

CCharPanel::CCharPanel ( const CCharPanel & ) {

}


QRectF CCharPanel::boundingRect() const {
	return QRectF ( 0, 0, 400, 300 );
}

void CCharPanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
                         QWidget * ) {
	painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
}

void CCharPanel::showPanel () {
	this->setVisible ( true );
	this->update();
}

void CCharPanel::hidePanel() {
	this->setVisible ( false );
}

void CCharPanel::setUpPanel ( CGameView *view ) {
	this->view=view;
	playerInventoryView = new CPlayerInventoryView ( view );
	playerInventoryView->setZValue ( 3 );
	playerInventoryView->setParentItem ( this );
	playerInventoryView->setAcceptDrops ( true );
	view->getScene()->addItem ( playerInventoryView );
	playerEquippedView = new CPlayerEquippedView ( view );
	playerEquippedView->setZValue ( 3 );
	playerEquippedView->setParentItem ( this );
	view->getScene()->addItem ( playerEquippedView );
}

void CCharPanel::update() {
	this->setPos (
	    view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
	                       view->height() / 2 - this->boundingRect().height() / 2 ) );
	playerInventoryView->setPos ( 0, 0 );
	playerEquippedView->setPos (
	    this->boundingRect().width() -
	    playerEquippedView->boundingRect().width(),
	    0 );
	playerInventoryView->update();
	playerEquippedView->update();
	QGraphicsItem::update();
}

QString CCharPanel::getPanelName() {
	return "CCharPanel";
}

void CCharPanel::onClickAction ( CGameObject *object ) {
	CItem*item=dynamic_cast<CItem*> ( object );
	if ( item ) {
		if ( item->isSingleUse() ) {
			item->getMap()->getEventHandler()->gameEvent ( item,  new CGameEventCaused ( CGameEvent::onUse,item->getMap()->getScene()->getPlayer() ) );
			item->getMap()->getScene()->getPlayer()->removeFromInventory ( item );
			delete item;
		} else {
			item->drag();
		}
	}
}
