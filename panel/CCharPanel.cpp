#include "CGamePanel.h"
#include "CGame.h"
#include "gui/CGui.h"
#include "object/CObject.h"
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

void CCharPanel::setUpPanel ( std::shared_ptr<CGameView> view ) {
    this->view=view;
    playerInventoryView = std::make_shared<CPlayerInventoryView> ( this->ptr<CCharPanel>() );
    playerInventoryView->setZValue ( 3 );
    playerInventoryView->setParentItem ( this );
    playerInventoryView->setAcceptDrops ( true );
    playerEquippedView = std::make_shared<CPlayerEquippedView> ( this->ptr<CCharPanel>() );
    playerEquippedView->setZValue ( 3 );
    playerEquippedView->setParentItem ( this );
}

void CCharPanel::update() {
    this->setPos (
        view.lock()->mapToScene ( view.lock()->width() / 2 - this->boundingRect().width() / 2,
                                  view.lock()->height() / 2 - this->boundingRect().height() / 2 ) );
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

void CCharPanel::onClickAction ( std::shared_ptr<CGameObject> object ) {
    std::shared_ptr<CItem> item=cast<CItem> ( object );
    if ( item ) {
        if ( item->isSingleUse() ) {
            item->getMap()->getEventHandler()->gameEvent ( item, std::make_shared<CGameEventCaused> ( CGameEvent::onUse,item->getMap()->getPlayer() ) );
            item->getMap()->getPlayer()->removeFromInventory ( item );
        } else {
            item->drag();
        }
    }
}

void CCharPanel::handleDrop ( std::shared_ptr<CPlayerView> view, std::shared_ptr<CGameObject> object ) {
    if ( view==playerInventoryView ) {
        std::shared_ptr<CItem> item=cast<CItem> ( object );
        if ( item ) {
            item->getMap()->getEventHandler()->gameEvent ( item ,std::make_shared<CGameEventCaused> ( CGameEvent::onUse,item->getMap()->getPlayer() ) );
        }
    }
}
