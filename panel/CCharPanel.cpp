#include "CGamePanel.h"
#include "CGame.h"
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
    playerInventoryView = new CPlayerInventoryView ( this );
    playerInventoryView->setZValue ( 3 );
    playerInventoryView->setParentItem ( this );
    playerInventoryView->setAcceptDrops ( true );
    playerEquippedView = new CPlayerEquippedView ( this );
    playerEquippedView->setZValue ( 3 );
    playerEquippedView->setParentItem ( this );
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
            item->getMap()->getEventHandler()->gameEvent ( item,  new CGameEventCaused ( CGameEvent::onUse,item->getMap()->getPlayer() ) );
            item->getMap()->getPlayer()->removeFromInventory ( item );
            delete item;
        } else {
            item->drag();
        }
    }
}

void CCharPanel::handleDrop ( CPlayerView *view, CGameObject *object ) {
    if ( view==playerInventoryView ) {
        CItem *item = dynamic_cast<CItem*> (  object );
        if ( item ) {
            item->getMap()->getEventHandler()->gameEvent ( item , new CGameEventCaused ( CGameEvent::onUse,item->getMap()->getPlayer() ) );
        }
    }
}
