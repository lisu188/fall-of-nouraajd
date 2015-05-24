#include "CTradePanel.h"
#include "CGame.h"
#include "gui/CGui.h"

CTradePanel::CTradePanel() {
    this->setZValue ( 8 );
}

void CTradePanel::showPanel() {
    this->setVisible ( true );
    this->setPos (
        view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
                           view->height() / 2 - this->boundingRect().height() / 2 ) );
    this->update();
}

void CTradePanel::hidePanel() {
    this->setVisible ( false );
}

void CTradePanel::update() {
    this->setPos (
        view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
                           view->height() / 2 - this->boundingRect().height() / 2 ) );
    playerInventoryView->setPos ( 0, 0 );
    tradeItemsView->setPos (
        this->boundingRect().width() -
        tradeItemsView->boundingRect().width(),
        0 );
    playerInventoryView->update();
    tradeItemsView->update();
    QGraphicsItem::update();
}

void CTradePanel::setUpPanel ( CGameView *view ) {
    this->view=view;
    this->playerInventoryView= new CPlayerInventoryView ( this );
    this->tradeItemsView=new CTradeItemsView ( this );

    playerInventoryView->setZValue ( 3 );
    playerInventoryView->setParentItem ( this );
    playerInventoryView->setAcceptDrops ( true );

    tradeItemsView->setZValue ( 3 );
    tradeItemsView->setParentItem ( this );
    tradeItemsView->setAcceptDrops ( true );
}

QString CTradePanel::getPanelName() {
    return "CTradePanel";
}


QRectF CTradePanel::boundingRect() const {
    return QRectF ( 0, 0, 400, 300 );
}

void CTradePanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * ) {
    painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
}

void CTradePanel::onClickAction ( std::shared_ptr<CGameObject> object ) {
    if ( std::shared_ptr<CItem> item=cast<CItem> ( object ) ) {
        item->drag();
    }
}

void CTradePanel::handleDrop ( CPlayerView *view, std::shared_ptr<CGameObject> object ) {
    CPlayerView *view2=dynamic_cast<CPlayerView*> ( object->parentItem() );
    if ( auto item=cast<CItem> ( object ) ) {
        auto player=this->getView()->getGame()->getMap()->getPlayer();
        if ( player ) {
            auto market=player->getMarket();
            if ( market ) {
                if ( view==playerInventoryView&&view2==tradeItemsView ) {
                    int cost=item->getPower() * ( item->getPower()+1 ) *market->getSell() ;
                    if ( player->getGold() >=cost ) {
                        player->addItem ( item );
                        market->remove ( item );
                        player->takeGold ( cost );
                    }
                } else  if ( view==tradeItemsView&&view2==playerInventoryView ) {
                    int cost=item->getPower() * ( item->getPower()+1 ) *market->getBuy() ;
                    player->removeFromInventory ( item );
                    market->add ( item );
                    player->addGold ( cost );
                }
                qDebug() <<player->getGold() <<"\n";
                this->update();
            }
        }
    }
}
